"""
Metadata reading and writing engine for media files.

Supports:
- Audio: MP3, FLAC, WAV, OGG, M4A via mutagen
- Video: MP4, MKV, AVI, WebM via pymediainfo
- Images: Basic EXIF data
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

try:
    from mutagen._file import File as MutagenFile
    from mutagen.easyid3 import EasyID3
    from mutagen.flac import FLAC
    from mutagen.id3 import ID3
    from mutagen.id3._util import ID3NoHeaderError
    from mutagen.mp4 import MP4
    MUTAGEN_AVAILABLE = True
except ImportError:
    MutagenFile = None  # type: ignore[assignment]
    EasyID3 = None  # type: ignore[assignment]
    FLAC = None  # type: ignore[assignment]
    ID3 = None  # type: ignore[assignment]
    ID3NoHeaderError = None  # type: ignore[assignment]
    MP4 = None  # type: ignore[assignment]
    MUTAGEN_AVAILABLE = False

try:
    from pymediainfo import MediaInfo
    PYMEDIAINFO_AVAILABLE = True
except ImportError:
    MediaInfo = None  # type: ignore[assignment]
    PYMEDIAINFO_AVAILABLE = False

if TYPE_CHECKING:
    from mutagen.easyid3 import EasyID3 as EasyID3Type
else:
    EasyID3Type = Any


@dataclass
class MediaMetadata:
    """Universal metadata container for all media types."""
    
    # File information (read-only)
    path: str = ""
    filename: str = ""
    filesize: int = 0
    format: str = ""
    duration: Optional[float] = None  # seconds
    
    # Common metadata (editable)
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    album_artist: Optional[str] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    comment: Optional[str] = None
    
    # Audio-specific
    track_number: Optional[int] = None
    track_total: Optional[int] = None
    disc_number: Optional[int] = None
    disc_total: Optional[int] = None
    composer: Optional[str] = None
    
    # Video-specific
    director: Optional[str] = None
    actors: List[str] = field(default_factory=list)
    description: Optional[str] = None
    
    # Technical info (read-only)
    bitrate: Optional[int] = None  # kbps
    sample_rate: Optional[int] = None  # Hz
    channels: Optional[int] = None
    codec: Optional[str] = None
    resolution: Optional[str] = None  # e.g., "1920x1080"
    
    # Rating and tags
    rating: Optional[int] = None  # 0-5 stars
    tags: List[str] = field(default_factory=list)
    
    # Timestamps
    date_added: Optional[datetime] = None
    date_modified: Optional[datetime] = None

    # Enrichment / external metadata (optional, filled by online scrapers)
    # External identifiers
    musicbrainz_track_id: Optional[str] = None
    musicbrainz_release_id: Optional[str] = None
    tmdb_id: Optional[str] = None  # For movies/TV
    imdb_id: Optional[str] = None  # For cross-reference

    # Original / canonical titles & extended descriptions
    original_title: Optional[str] = None
    overview: Optional[str] = None  # Longer plot/album/track overview fetched externally

    # Provenance
    enrichment_sources: List[str] = field(default_factory=list)  # Providers that contributed
    enrichment_fetched_at: Optional[datetime] = None  # Last successful enrichment timestamp
    enrichment_confidence: Optional[float] = None  # 0..1 aggregated confidence score
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "path": self.path,
            "filename": self.filename,
            "filesize": self.filesize,
            "format": self.format,
            "duration": self.duration,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "album_artist": self.album_artist,
            "year": self.year,
            "genre": self.genre,
            "comment": self.comment,
            "track_number": self.track_number,
            "track_total": self.track_total,
            "disc_number": self.disc_number,
            "disc_total": self.disc_total,
            "composer": self.composer,
            "director": self.director,
            "actors": self.actors,
            "description": self.description,
            "bitrate": self.bitrate,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "codec": self.codec,
            "resolution": self.resolution,
            "rating": self.rating,
            "tags": self.tags,
            "date_added": self.date_added.isoformat() if self.date_added else None,
            "date_modified": self.date_modified.isoformat() if self.date_modified else None,
            # Enrichment fields (persisted but optional)
            "musicbrainz_track_id": self.musicbrainz_track_id,
            "musicbrainz_release_id": self.musicbrainz_release_id,
            "tmdb_id": self.tmdb_id,
            "imdb_id": self.imdb_id,
            "original_title": self.original_title,
            "overview": self.overview,
            "enrichment_sources": self.enrichment_sources,
            "enrichment_fetched_at": self.enrichment_fetched_at.isoformat() if self.enrichment_fetched_at else None,
            "enrichment_confidence": self.enrichment_confidence,
        }


class MetadataReader:
    """Read metadata from media files."""
    
    def __init__(self) -> None:
        self.mutagen_available = MUTAGEN_AVAILABLE
        self.pymediainfo_available = PYMEDIAINFO_AVAILABLE
    
    def read(self, file_path: Path) -> MediaMetadata:
        """
        Read metadata from a file.
        
        Args:
            file_path: Path to the media file
            
        Returns:
            MediaMetadata object with extracted information
        """
        metadata = MediaMetadata()
        metadata.path = str(file_path)
        metadata.filename = file_path.name
        
        if not file_path.exists():
            return metadata
        
        metadata.filesize = file_path.stat().st_size
        metadata.date_modified = datetime.fromtimestamp(file_path.stat().st_mtime)
        
        # Detect file type and read accordingly
        suffix = file_path.suffix.lower()
        
        if suffix in {".mp3", ".flac", ".ogg", ".m4a", ".wav"}:
            self._read_audio(file_path, metadata)
        elif suffix in {".mp4", ".mkv", ".avi", ".webm", ".mov"}:
            self._read_video(file_path, metadata)
        elif suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
            self._read_image(file_path, metadata)
        
        return metadata
    
    def _read_audio(self, file_path: Path, metadata: MediaMetadata) -> None:
        """Read audio file metadata using mutagen."""
        if not self.mutagen_available:
            metadata.format = "audio"
            return

        if MutagenFile is None:
            metadata.format = "audio"
            return
        
        try:
            audio = MutagenFile(str(file_path), easy=True)
            if audio is None:
                return
            
            metadata.format = "audio"
            
            # Duration
            if hasattr(audio.info, "length"):
                metadata.duration = float(audio.info.length)
            
            # Bitrate
            if hasattr(audio.info, "bitrate"):
                metadata.bitrate = int(audio.info.bitrate / 1000)  # Convert to kbps
            
            # Sample rate
            if hasattr(audio.info, "sample_rate"):
                metadata.sample_rate = audio.info.sample_rate
            
            # Channels
            if hasattr(audio.info, "channels"):
                metadata.channels = audio.info.channels
            
            # Tags
            if hasattr(audio, "tags") and audio.tags:
                metadata.title = self._get_tag(audio.tags, "title")
                metadata.artist = self._get_tag(audio.tags, "artist")
                metadata.album = self._get_tag(audio.tags, "album")
                metadata.album_artist = self._get_tag(audio.tags, "albumartist")
                metadata.genre = self._get_tag(audio.tags, "genre")
                metadata.comment = self._get_tag(audio.tags, "comment")
                metadata.composer = self._get_tag(audio.tags, "composer")
                
                # Year
                year_str = self._get_tag(audio.tags, "date")
                if year_str:
                    try:
                        metadata.year = int(year_str[:4])
                    except (ValueError, TypeError):
                        pass
                
                # Track number
                track_str = self._get_tag(audio.tags, "tracknumber")
                if track_str:
                    try:
                        if "/" in track_str:
                            track, total = track_str.split("/", 1)
                            metadata.track_number = int(track)
                            metadata.track_total = int(total)
                        else:
                            metadata.track_number = int(track_str)
                    except (ValueError, TypeError):
                        pass
                
                # Disc number
                disc_str = self._get_tag(audio.tags, "discnumber")
                if disc_str:
                    try:
                        if "/" in disc_str:
                            disc, total = disc_str.split("/", 1)
                            metadata.disc_number = int(disc)
                            metadata.disc_total = int(total)
                        else:
                            metadata.disc_number = int(disc_str)
                    except (ValueError, TypeError):
                        pass
        
        except Exception as exc:
            # Silently fail, return partial metadata
            pass
    
    def _read_video(self, file_path: Path, metadata: MediaMetadata) -> None:
        """Read video file metadata using pymediainfo."""
        if not self.pymediainfo_available:
            metadata.format = "video"
            return

        if MediaInfo is None:
            metadata.format = "video"
            return
        
        try:
            media_info = MediaInfo.parse(str(file_path))
            metadata.format = "video"
            
            for track in media_info.tracks:
                if track.track_type == "General":
                    # Duration in milliseconds
                    if track.duration:
                        metadata.duration = float(track.duration) / 1000.0
                    
                    # Bitrate
                    if track.overall_bit_rate:
                        metadata.bitrate = int(track.overall_bit_rate / 1000)
                    
                    # Title
                    if track.title:
                        metadata.title = track.title
                    
                    # Genre
                    if track.genre:
                        metadata.genre = track.genre
                    
                    # Comment/Description
                    if track.comment:
                        metadata.description = track.comment
                
                elif track.track_type == "Video":
                    # Resolution
                    if track.width and track.height:
                        metadata.resolution = f"{track.width}x{track.height}"
                    
                    # Codec
                    if track.codec:
                        metadata.codec = track.codec
                
                elif track.track_type == "Audio":
                    # Audio channels
                    if track.channel_s:
                        metadata.channels = track.channel_s
                    
                    # Sample rate
                    if track.sampling_rate:
                        metadata.sample_rate = int(track.sampling_rate)
        
        except Exception as exc:
            # Silently fail
            pass
    
    def _read_image(self, file_path: Path, metadata: MediaMetadata) -> None:
        """Read basic image metadata."""
        metadata.format = "image"
        # Could use PIL/Pillow here for EXIF data, but keeping it simple for now
    
    def _get_tag(self, tags: Any, key: str) -> Optional[str]:
        """Extract a tag value safely."""
        try:
            value = tags.get(key)
            if value:
                if isinstance(value, list):
                    return str(value[0]) if value else None
                return str(value)
        except (KeyError, AttributeError, TypeError):
            pass
        return None


class MetadataWriter:
    """Write metadata back to media files."""
    
    def __init__(self) -> None:
        self.mutagen_available = MUTAGEN_AVAILABLE
    
    def write(self, file_path: Path, metadata: MediaMetadata) -> bool:
        """
        Write metadata to a file.
        
        Args:
            file_path: Path to the media file
            metadata: Metadata to write
            
        Returns:
            True if successful, False otherwise
        """
        if not file_path.exists():
            return False
        
        suffix = file_path.suffix.lower()
        
        if suffix in {".mp3", ".flac", ".ogg", ".m4a"}:
            return self._write_audio(file_path, metadata)
        elif suffix in {".mp4", ".mkv", ".avi", ".webm"}:
            return self._write_video(file_path, metadata)
        
        return False
    
    def _write_audio(self, file_path: Path, metadata: MediaMetadata) -> bool:
        """Write audio metadata using mutagen."""
        if not self.mutagen_available:
            return False

        suffix = file_path.suffix.lower()

        try:
            if suffix == ".mp3":
                return self._write_mp3(file_path, metadata)
            if suffix == ".flac":
                return self._write_flac(file_path, metadata)
            if suffix == ".ogg":
                return self._write_vorbis(file_path, metadata)
            if suffix == ".m4a":
                return self._write_mp4(file_path, metadata)
        except Exception:
            return False
        return False

    def _write_mp3(self, file_path: Path, metadata: MediaMetadata) -> bool:
        if EasyID3 is None or MutagenFile is None or ID3 is None or ID3NoHeaderError is None:
            return False
        try:
            try:
                tags = EasyID3(str(file_path))
            except ID3NoHeaderError:
                audio = MutagenFile(str(file_path))
                if audio is None:
                    audio = ID3()
                    audio.save(str(file_path))
                else:
                    audio.add_tags()
                    audio.save()
                tags = EasyID3(str(file_path))

            self._set_easy_tag(tags, "title", metadata.title)
            self._set_easy_tag(tags, "artist", metadata.artist)
            self._set_easy_tag(tags, "album", metadata.album)
            self._set_easy_tag(tags, "albumartist", metadata.album_artist)
            self._set_easy_tag(tags, "genre", metadata.genre)
            self._set_easy_tag(tags, "comment", metadata.comment)
            self._set_easy_tag(tags, "composer", metadata.composer)

            if metadata.year:
                self._set_easy_tag(tags, "date", str(metadata.year))
            else:
                self._clear_easy_tag(tags, "date")

            if metadata.track_number:
                track_value = f"{metadata.track_number}/{metadata.track_total}" if metadata.track_total else str(metadata.track_number)
                self._set_easy_tag(tags, "tracknumber", track_value)
            else:
                self._clear_easy_tag(tags, "tracknumber")

            if metadata.disc_number:
                disc_value = f"{metadata.disc_number}/{metadata.disc_total}" if metadata.disc_total else str(metadata.disc_number)
                self._set_easy_tag(tags, "discnumber", disc_value)
            else:
                self._clear_easy_tag(tags, "discnumber")

            tags.save()
            return True
        except Exception:
            return False

    def _write_flac(self, file_path: Path, metadata: MediaMetadata) -> bool:
        if FLAC is None:
            return False
        try:
            audio = FLAC(str(file_path))
        except Exception:
            return False

        self._set_mutagen_list_tag(audio, "title", metadata.title)
        self._set_mutagen_list_tag(audio, "artist", metadata.artist)
        self._set_mutagen_list_tag(audio, "album", metadata.album)
        self._set_mutagen_list_tag(audio, "albumartist", metadata.album_artist)
        self._set_mutagen_list_tag(audio, "genre", metadata.genre)
        self._set_mutagen_list_tag(audio, "comment", metadata.comment)
        self._set_mutagen_list_tag(audio, "composer", metadata.composer)

        if metadata.year:
            audio["date"] = [str(metadata.year)]
        elif "date" in audio:
            del audio["date"]

        if metadata.track_number:
            audio["tracknumber"] = [str(metadata.track_number)]
        elif "tracknumber" in audio:
            del audio["tracknumber"]

        if metadata.track_total:
            audio["totaltracks"] = [str(metadata.track_total)]
        elif "totaltracks" in audio:
            del audio["totaltracks"]

        if metadata.disc_number:
            audio["discnumber"] = [str(metadata.disc_number)]
        elif "discnumber" in audio:
            del audio["discnumber"]

        if metadata.disc_total:
            audio["totaldiscs"] = [str(metadata.disc_total)]
        elif "totaldiscs" in audio:
            del audio["totaldiscs"]

        try:
            audio.save()
            return True
        except Exception:
            return False

    def _write_vorbis(self, file_path: Path, metadata: MediaMetadata) -> bool:
        if MutagenFile is None:
            return False

        audio = MutagenFile(str(file_path))
        if audio is None or not hasattr(audio, "tags"):
            return False

        self._set_mutagen_list_tag(audio, "title", metadata.title)
        self._set_mutagen_list_tag(audio, "artist", metadata.artist)
        self._set_mutagen_list_tag(audio, "album", metadata.album)
        self._set_mutagen_list_tag(audio, "albumartist", metadata.album_artist)
        self._set_mutagen_list_tag(audio, "genre", metadata.genre)
        self._set_mutagen_list_tag(audio, "comment", metadata.comment)
        self._set_mutagen_list_tag(audio, "composer", metadata.composer)

        if metadata.year:
            audio["date"] = [str(metadata.year)]
        elif "date" in audio:
            del audio["date"]

        if metadata.track_number:
            audio["tracknumber"] = [str(metadata.track_number)]
        elif "tracknumber" in audio:
            del audio["tracknumber"]

        if metadata.track_total:
            audio["totaltracks"] = [str(metadata.track_total)]
        elif "totaltracks" in audio:
            del audio["totaltracks"]

        if metadata.disc_number:
            audio["discnumber"] = [str(metadata.disc_number)]
        elif "discnumber" in audio:
            del audio["discnumber"]

        if metadata.disc_total:
            audio["totaldiscs"] = [str(metadata.disc_total)]
        elif "totaldiscs" in audio:
            del audio["totaldiscs"]

        try:
            audio.save()
            return True
        except Exception:
            return False

    def _write_mp4(self, file_path: Path, metadata: MediaMetadata) -> bool:
        if MP4 is None:
            return False
        try:
            audio = MP4(str(file_path))
        except Exception:
            return False

        mapping = {
            "\u00a9nam": metadata.title,
            "\u00a9ART": metadata.artist,
            "\u00a9alb": metadata.album,
            "aART": metadata.album_artist,
            "\u00a9gen": metadata.genre,
            "\u00a9cmt": metadata.comment,
            "\u00a9wrt": metadata.composer,
        }

        for key, value in mapping.items():
            if value:
                audio[key] = [value]
            elif key in audio:
                del audio[key]

        if metadata.year:
            audio["\u00a9day"] = [str(metadata.year)]
        elif "\u00a9day" in audio:
            del audio["\u00a9day"]

        if metadata.track_number:
            audio["trkn"] = [(metadata.track_number, metadata.track_total or 0)]
        elif "trkn" in audio:
            del audio["trkn"]

        if metadata.disc_number:
            audio["disk"] = [(metadata.disc_number, metadata.disc_total or 0)]
        elif "disk" in audio:
            del audio["disk"]

        try:
            audio.save()
            return True
        except Exception:
            return False
    
    def _write_video(self, file_path: Path, metadata: MediaMetadata) -> bool:
        """Write video metadata (limited support)."""
        # Video metadata writing is complex and format-specific
        # Most video metadata is read-only or requires specialized tools
        # For now, we'll skip video writing
        return False
    
    def _set_tag(self, tags: Any, key: str, value: Optional[str]) -> None:
        """Set a tag value safely."""
        try:
            if value:
                tags[key] = value
            elif key in tags:
                del tags[key]
        except (KeyError, AttributeError, TypeError):
            pass

    def _set_easy_tag(self, tags: EasyID3Type, key: str, value: Optional[str]) -> None:
        if value is None or value == "":
            self._clear_easy_tag(tags, key)
            return
        tags[key] = [value]

    def _clear_easy_tag(self, tags: EasyID3Type, key: str) -> None:
        try:
            if key in tags:
                del tags[key]
        except KeyError:
            pass

    def _set_mutagen_list_tag(self, tags: Any, key: str, value: Optional[str]) -> None:
        try:
            if value:
                tags[key] = [value]
            elif key in tags:
                del tags[key]
        except Exception:
            pass
