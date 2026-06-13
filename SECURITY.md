# Security

This project controls a real power switch. Please treat credentials and device IDs as sensitive local data.

## Sensitive Files

The following files should stay local and are ignored by Git:

- `config.json`
- `.mi_credentials.json`
- `devices_tokens.json`
- `charger_log.txt`

Do not paste these files into issues or pull requests.

## Reporting Security Issues

Please do not open a public issue for credential leaks, unsafe default behavior, or remote-control vulnerabilities.

Instead, contact the maintainer privately through GitHub and include:

- affected file or feature;
- reproduction steps;
- whether real credentials or device IDs were exposed;
- suggested mitigation if you have one.

## Operational Safety

- Test with the Mi Home app nearby so you can manually switch the plug.
- Avoid rapid threshold changes that could toggle power repeatedly.
- Use the shutdown task only after confirming normal charging control works.
