"""
Unit tests for Unsigned IPA Release Asset Validator.
"""

import sys
import plistlib
import tempfile
import unittest
import zipfile
from pathlib import Path

# Ensure repo root is on sys.path for scripts import
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.validate_ipa import (
    validate_ipa,
    REQUIRED_BUNDLE_ID,
    EXPECTED_APP_BUNDLE_NAME,
    EXPECTED_VERSION,
    EXPECTED_BUILD,
)


class TestIPAValidation(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.dir_path = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_mock_ipa(
        self,
        filename: str = "AgentCore-iOS-v0.1.0-unsigned.ipa",
        include_payload: bool = True,
        include_app: bool = True,
        app_name: str = EXPECTED_APP_BUNDLE_NAME,
        bundle_id: str = REQUIRED_BUNDLE_ID,
        version: str = EXPECTED_VERSION,
        build: str = EXPECTED_BUILD,
        include_plist: bool = True,
        include_binary: bool = True,
        binary_size: int = 1024,
        extra_app: bool = False,
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
                prefix = f"Payload/{app_name}/"
                if include_plist:
                    zf.writestr(prefix + "Info.plist", plistlib.dumps(plist_data))
                if include_binary:
                    zf.writestr(prefix + "AgentCoreIOS", b"A" * binary_size)
                if extra_app:
                    zf.writestr("Payload/Extra.app/Info.plist", plistlib.dumps(plist_data))
            elif include_payload:
                zf.writestr("Payload/some_file.txt", "data")

        return ipa_path

    def test_valid_unsigned_ipa(self):
        ipa_path = self._create_mock_ipa("AgentCore-iOS-v0.1.0-unsigned.ipa")
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

    def test_multiple_app_bundles(self):
        ipa_path = self._create_mock_ipa(extra_app=True)
        with self.assertRaises(ValueError) as ctx:
            validate_ipa(str(ipa_path))
        self.assertIn("Expected exactly 1 .app bundle inside Payload/", str(ctx.exception))

    def test_wrong_app_bundle_name(self):
        ipa_path = self._create_mock_ipa(app_name="WrongName.app")
        with self.assertRaises(ValueError) as ctx:
            validate_ipa(str(ipa_path))
        self.assertIn("Expected app bundle name 'AgentCoreIOS.app'", str(ctx.exception))

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

    def test_version_mismatch(self):
        ipa_path = self._create_mock_ipa(version="9.9.9")
        with self.assertRaises(ValueError) as ctx:
            validate_ipa(str(ipa_path))
        self.assertIn("Version mismatch", str(ctx.exception))

    def test_build_mismatch(self):
        ipa_path = self._create_mock_ipa(build="99")
        with self.assertRaises(ValueError) as ctx:
            validate_ipa(str(ipa_path))
        self.assertIn("Build number mismatch", str(ctx.exception))

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
