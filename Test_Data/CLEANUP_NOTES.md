Cleanup performed on 2025-08-14:

- Removed AD mentions from exporter and README.
- Implemented username-based location mapping via mapping.json.
- Fixed indentation/syntax errors in flexlm_exporter.py.
- Trimmed mapping.json to a small, valid set for demo; extend as needed.
- Removed ldap3 from requirements.txt.
- Note: test_username_location.py remains and should be deleted if tests must not be included. test_without_ad.py and ENHANCED_AD_INTEGRATION.md are legacy docs and can be deleted if not needed.
