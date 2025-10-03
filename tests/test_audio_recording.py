import pytest

from mmst.plugins.audio_tools.recording import RecordingController

np = pytest.importorskip("numpy")


def test_convert_float_buffer_to_int16():
    controller = RecordingController(force_placeholder=True)
    data = np.array([[0.0, 0.5], [-0.5, 1.0]], dtype=np.float32)
    pcm_bytes = controller._convert_float_buffer(data, 2)
    assert len(pcm_bytes) == data.size * 2
    pcm_array = np.frombuffer(pcm_bytes, dtype="<i2")
    assert pcm_array.max() > 0
    assert pcm_array.min() < 0


def test_convert_float_buffer_to_int32():
    controller = RecordingController(force_placeholder=True)
    data = np.linspace(-1.0, 1.0, num=8, dtype=np.float32).reshape(4, 2)
    pcm_bytes = controller._convert_float_buffer(data, 4)
    assert len(pcm_bytes) == data.size * 4
    pcm_array = np.frombuffer(pcm_bytes, dtype="<i4")
    assert pcm_array.max() > pcm_array.min()
    assert len(set(pcm_array.tolist())) > 1
