#!/bin/bash
# Generate sitemap and copy to frontend every three hours
LOGFILE="/root/Manhua-Frontend-BackendAPI/update_sitemaps.log"

{
	echo "--- $(date) ---"
	echo "Running sitemap generation..."
	python /root/Manhua-Frontend-BackendAPI/generate_sitemap_split.py
	echo "Copying sitemap files..."
	cp /root/Manhua-Frontend-BackendAPI/sitemaps/*.xml ~/Manhua-Frontend/public/sitemaps/
	cp /root/Manhua-Frontend-BackendAPI/sitemap-index.xml ~/Manhua-Frontend/public/
	echo "Done."
} >> "$LOGFILE" 2>&1
