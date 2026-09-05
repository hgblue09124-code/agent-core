"""
Unit tests for IPA Release Asset Validator.
"""

import sys
import plistlib
import tempfile
import unittest
import zipfile
from pathlib import Path

# Ensure repo root is on sys.path for scripts import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.validate_ipa import validate_ipa, REQUIRED_BUNDLE_IDS


class TestIPAValidation(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_mock_ipa(
        self,
        filename: str = "AgentCore-iOS-v0.1.0.ipa",
        include_payload: bool = True,
        include_app: bool = True,
        bundle_id: str = "com.agentcore.AgentCoreIOS",
        version: str = "0.1.0",
        build: str = "1",
        include_plist: bool = True,
        include_binary: bool = True,
        binary_size: int = 1024,
        corrupt_zip: bool = False,
    ) -> Path:
        ipa_path = self.dir_path / filename

        if corrupt_zip:
            ipa_path.write_bytes(b"NOT_A_VALID_ZIP_FILE_DATA")
            return ipa_path

        plist_data = {
            "CFBundleIdentifier": bundle_id,
            "CFBundleShortVersionString": version,
            "CFBundleVersion": build,
            "CFBundleExecutable": "AgentCoreIOS",
        }

        with zipfile.ZipFile(ipa_path, "w") as zf:
            if include_payload and include_app:
                prefix = "Payload/AgentCoreIOS.app/"
                if include_plist:
                    zf.writestr(prefix + "Info.plist", plistlib.dumps(plist_data))
                if include_binary:
                    zf.writestr(prefix + "AgentCoreIOS", b"A" * binary_size)
            elif include_payload:
                zf.writestr("Payload/some_file.txt", "data")

        return ipa_path

    def test_valid_ipa(self):
        ipa_path = self._create_mock_ipa()
        # Should not raise
        validate_ipa(str(ipa_path))

    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            validate_ipa(str(self.dir_path / "nonexistent.ipa"))

    def test_invalid_extension(self):
        invalid_path = self.dir_path / "app.zip"
        invalid_path.write_text("test")
        with self.assertRaises(ValueError) as ctx:
            validate_ipa(str(invalid_path))
        self.assertIn("File extension must be .ipa", str(ctx.exception))

    def test_corrupt_zip(self):
        ipa_path = self._create_mock_ipa(corrupt_zip=True)
        with self.assertRaises(ValueError) as ctx:
            validate_ipa(str(ipa_path))
        self.assertIn("Corrupt or invalid ZIP format", str(ctx.exception))

    def test_missing_payload(self):
        ipa_path = self._create_mock_ipa(include_payload=False)
        with self.assertRaises(ValueError) as ctx:
            validate_ipa(str(ipa_path))
        self.assertIn("does not contain a 'Payload/' directory", str(ctx.exception))

    def test_missing_app_bundle(self):
        ipa_path = self._create_mock_ipa(include_app=False)
        with self.assertRaises(ValueError) as ctx:
            validate_ipa(str(ipa_path))
        self.assertIn("No .app bundle found inside Payload/", str(ctx.exception))

    def test_missing_info_plist(self):
        ipa_path = self._create_mock_ipa(include_plist=False)
        with self.assertRaises(ValueError) as ctx:
            validate_ipa(str(ipa_path))
        self.assertIn("Info.plist missing", str(ctx.exception))

    def test_bundle_id_mismatch(self):
        ipa_path = self._create_mock_ipa(bundle_id="com.wrong.bundle")
        with self.assertRaises(ValueError) as ctx:
            validate_ipa(str(ipa_path))
        self.assertIn("Bundle ID mismatch", str(ctx.exception))

    def test_missing_executable_binary(self):
        ipa_path = self._create_mock_ipa(include_binary=False)
        with self.assertRaises(ValueError) as ctx:
            validate_ipa(str(ipa_path))
        self.assertIn("Executable binary missing", str(ctx.exception))

    def test_empty_executable_binary(self):
        ipa_path = self._create_mock_ipa(binary_size=0)
        with self.assertRaises(ValueError) as ctx:
            validate_ipa(str(ipa_path))
        self.assertIn("Executable binary at Payload/AgentCoreIOS.app/AgentCoreIOS is empty", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
