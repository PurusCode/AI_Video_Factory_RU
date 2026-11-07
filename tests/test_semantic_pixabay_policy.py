import inspect
from video_farm import pixabay_media

def test_pixabay_adapter_does_not_call_pexels_endpoint():
    source = inspect.getsource(pixabay_media).lower()
    assert "pexels.com" not in source
    assert "pixabay.com/api" in source
