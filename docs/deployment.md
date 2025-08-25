# Deployment & File Transfer

## Deployment Steps
- Ensure backend and frontend environments are set up
- Start MongoDB and Redis
- Run FastAPI backend (`uvicorn main:app --reload`)
- Automate sitemap generation and transfer

## File Transfer
- Local: use `cp` as above
- Remote: use `scp` or `rsync`

## Permissions
- Ensure sitemap files are world-readable (`chmod 644`)
- Ensure frontend public directory is accessible

## Cron Automation
- See `sitemap_automation.md` for cron setup
