
#!/bin/bash
# Generalized sitemap update script
# Load environment variables from .env if present
if [ -f .env ]; then
	set -a
	. ./.env
	set +a
fi

BACKEND_DIR="${BACKEND_DIR:-$(pwd)}"
FRONTEND_DIR="${FRONTEND_DIR:-$BACKEND_DIR/../Manhua-Frontend}"
LOGFILE="$BACKEND_DIR/update_sitemaps.log"

{
	echo "--- $(date) ---"
	echo "Running sitemap generation..."
	python "$BACKEND_DIR/generate_sitemap_split.py"
	echo "Copying sitemap files..."
	mkdir -p "$FRONTEND_DIR/public/sitemaps"
	cp "$BACKEND_DIR/sitemaps"/*.xml "$FRONTEND_DIR/public/sitemaps/"
	cp "$BACKEND_DIR/sitemap-index.xml" "$FRONTEND_DIR/public/"
	echo "Done."
} >> "$LOGFILE" 2>&1



