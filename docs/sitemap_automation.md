# Sitemap Automation

## Generation
- Script: `generate_sitemap_split.py`
- Splits sitemaps into multiple files (≤49,000 URLs each)
- Ensures valid date format and URL encoding
- Handles special characters in slugs/names

## Automation
- Shell script: `update_sitemaps.sh`
- Use cron to run every 3 hours:
  ```bash
  0 */3 * * * bash /root/Manhua-Frontend-BackendAPI/update_sitemaps.sh
  ```
- Logs output to `update_sitemaps.log`

## Troubleshooting
- Check log for errors
- Validate XML with online tools or `xmllint`
- Ensure file permissions and public access

See script files for details.
