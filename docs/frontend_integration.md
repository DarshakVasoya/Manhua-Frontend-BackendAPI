# Frontend Integration

## Static File Handling
- Sitemaps and index should be placed in the frontend's public directory (e.g., `public/sitemaps/`)
- No need to rebuild frontend unless static files are processed during build

## File Transfer
- Use `cp` for local copy
- Use `scp` for remote transfer

## Serving Sitemaps
- Static hosting (Nginx, Apache, Vercel, etc.) will serve `.xml` files with correct headers
- If using a custom route, set header: `Content-Type: application/xml`

## Example
```bash
cp /root/Manhua-Frontend-BackendAPI/sitemaps/*.xml ~/Manhua-Frontend/public/sitemaps/
cp /root/Manhua-Frontend-BackendAPI/sitemap-index.xml ~/Manhua-Frontend/public/
```
