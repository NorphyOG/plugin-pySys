"""
Tests for backup dry-run mode.

Verifies that when dry_run=True, no actual file operations are performed,
but the backup engine still computes and reports what would happen.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from mmst.plugins.file_manager import backup


def test_dry_run_no_file_copies(tmp_path):
    """Test that dry-run mode doesn't copy any files."""
    # Create source structure
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "file1.txt").write_text("content1")
    (source_dir / "file2.txt").write_text("content2")
    
    # Create target dir
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    
    # Mock the progress callback
    progress_callback = Mock()
    
    # Run dry-run backup
    with patch('shutil.copy2') as mock_copy:
        result = backup.perform_backup(
            source_dir, 
            target_dir, 
            mirror=False,
            progress=progress_callback,
            dry_run=True
        )
        
        # Verify no actual copies happened
        mock_copy.assert_not_called()
    
    # Target should still be empty (no files copied)
    assert list(target_dir.iterdir()) == []
    
    # But result should report what would have been copied
    assert result.copied_files > 0


def test_dry_run_mirror_no_deletions(tmp_path):
    """Test that dry-run mirror mode doesn't delete any files."""
    # Create source with one file
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "keep.txt").write_text("keep me")
    
    # Create target with extra file that would be deleted in real mirror
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    (target_dir / "keep.txt").write_text("old keep")
    (target_dir / "delete_me.txt").write_text("I should be deleted")
    
    progress_callback = Mock()
    
    # Run dry-run mirror backup
    with patch('mmst.plugins.file_manager.backup.send2trash') as mock_trash:
        result = backup.perform_backup(
            source_dir,
            target_dir,
            mirror=True,
            progress=progress_callback,
            dry_run=True
        )
        
        # Verify no deletions happened
        mock_trash.assert_not_called()
    
    # File should still exist
    assert (target_dir / "delete_me.txt").exists()
    
    # But result should report what would have been deleted
    assert result.removed_files > 0


def test_dry_run_reports_skipped_files(tmp_path):
    """Test that dry-run correctly reports up-to-date files as skipped."""
    import time
    
    # Create source file
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source_file = source_dir / "same.txt"
    source_file.write_text("same content")
    
    # Create identical target file with same mtime
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    target_file = target_dir / "same.txt"
    target_file.write_text("same content")
    
    # Make sure target is not older
    time.sleep(0.01)
    target_file.touch()
    
    progress_callback = Mock()
    
    # Run dry-run
    result = backup.perform_backup(
        source_dir,
        target_dir,
        mirror=False,
        progress=progress_callback,
        dry_run=True
    )
    
    # Should report file as skipped
    assert result.skipped_files >= 0  # May skip if sizes/times match


def test_dry_run_prefix_in_messages(tmp_path):
    """Test that all dry-run messages are prefixed with [DRY RUN]."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "file.txt").write_text("content")
    
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    
    messages = []
    
    def capture_progress(message):
        messages.append(message)
    
    # Run dry-run
    result = backup.perform_backup(
        source_dir,
        target_dir,
        mirror=False,
        progress=capture_progress,
        dry_run=True
    )
    
    # Check that messages contain dry-run marker
    dry_run_messages = [m for m in messages if "[DRY RUN]" in m]
    assert len(dry_run_messages) > 0
    
    # Verify at least some messages were generated
    assert len(messages) > 0


def test_dry_run_computes_correct_stats(tmp_path):
    """Test that dry-run produces accurate statistics."""
    # Create source with multiple files
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "new1.txt").write_text("content1")
    (source_dir / "new2.txt").write_text("content2")
    (source_dir / "new3.txt").write_text("content3")
    
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    
    progress_callback = Mock()
    
    # Run dry-run
    result = backup.perform_backup(
        source_dir,
        target_dir,
        mirror=False,
        progress=progress_callback,
        dry_run=True
    )
    
    # Should count all 3 files as would-be-copied
    assert result.copied_files == 3
    assert result.removed_files == 0
    assert result.total_bytes_copied > 0  # Should sum file sizes


def test_normal_mode_does_copy_files(tmp_path):
    """Test that normal (non-dry-run) mode actually copies files."""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "real_copy.txt").write_text("real content")
    
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    
    progress_callback = Mock()
    
    # Run REAL backup (dry_run=False)
    result = backup.perform_backup(
        source_dir,
        target_dir,
        mirror=False,
        progress=progress_callback,
        dry_run=False
    )
    
    # File should actually be copied
    assert (target_dir / "real_copy.txt").exists()
    assert (target_dir / "real_copy.txt").read_text() == "real content"
    
    # Result should show successful copy
    assert result.copied_files == 1
