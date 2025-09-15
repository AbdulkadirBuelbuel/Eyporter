Username-based location mapping

- Location is derived from the username: characters after the last digit form a location code.
  Examples: bla99bng -> code bng; user123fra -> code fra; test42muc -> code muc.
- Codes are mapped to full names via mapping.json at the repo root (same folder as exporter).
- If a code is missing, location is reported as "Unknown".

How to extend mapping

- Edit mapping.json and add entries under location_mapping.
- Keep codes lowercase, unique, and 2–5 letters.
- Restart the exporter or send SIGHUP-equivalent (not implemented) to reload; current version loads on startup only.
