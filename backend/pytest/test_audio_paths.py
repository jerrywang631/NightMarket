"""
Tests for audio path handling. The DB holds paths from whichever machine ran TTS
(Linux /mnt/nfs/..., Windows C:\\..., or relative audio-clips/...); the game and
admin page must get the same /audio-clips/<file> URL on any server OS.
"""

from managers.dialogue_manager import audio_filename, audio_url


class TestAudioPaths:

    def test_linux_absolute_path(self):
        path = "/mnt/nfs/riaru/Projects/NightMarket/backend/audio-clips/n_l0_pb_root.wav"
        assert audio_url(path) == "/audio-clips/n_l0_pb_root.wav"

    def test_windows_absolute_path(self):
        path = r"C:\Users\16367\Documents\GitHub\NightMarket\backend\audio-clips\n_l4_v2_greet.wav"
        assert audio_url(path) == "/audio-clips/n_l4_v2_greet.wav"

    def test_relative_path(self):
        assert audio_url("audio-clips/o_l4_v2_001.wav") == "/audio-clips/o_l4_v2_001.wav"

    def test_empty_path(self):
        assert audio_url("") == ""
        assert audio_url(None) == ""
        assert audio_filename(None) == ""
