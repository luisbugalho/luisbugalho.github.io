import os
from PIL import Image
from PIL.ExifTags import TAGS
import exifread
from geopy.geocoders import Nominatim
from geopy.exc import GeopyError
from datetime import datetime

# Configuration
photos_folder = "cascadedata"  # Replace with your folder path
output_file = "cascade2.md"  # Output markdown file
image_base_url = "/cascadedata/"  # Path where images are hosted on your site
thumbnail_folder = "cascadedata/thumbnails"  # Folder to save thumbnails
thumbnail_size = (200, 200)  # Maximum size for thumbnails
preamble_f = "cascade_intro.txt"  # Path to the text file containing the preamble


def import_preamble(preamble_file):
    """Read the preamble content from a text file."""
    try:
        with open(preamble_file, "r", encoding="utf-8") as file:
            return file.read()
    except Exception as e:
        print(f"Error reading preamble file: {e}")
        return ""

def get_exif_data(image_path):
    """Extract EXIF data from an image."""
    try:
        image = Image.open(image_path)
        exif_data = image._getexif()
        if not exif_data:
            return {}

        exif = {TAGS.get(tag, tag): value for tag, value in exif_data.items()}
        return exif
    except Exception as e:
        print(f"Error reading EXIF data from {image_path}: {e}")
        return {}


def get_exif_date_time(exif):
    """Get the capture date from EXIF data."""
    date_time = exif.get("DateTimeOriginal") or exif.get("DateTime")
    if date_time:
        try:
            return datetime.strptime(date_time, "%Y:%m:%d %H:%M:%S")
        except ValueError:
            return None
    return None


def get_gps_info(image_path):
    """Extract GPS data from EXIF metadata."""
    with open(image_path, 'rb') as f:
        tags = exifread.process_file(f, stop_tag="GPS GPSLatitude", details=False)
        lat = tags.get("GPS GPSLatitude")
        lat_ref = tags.get("GPS GPSLatitudeRef")
        lon = tags.get("GPS GPSLongitude")
        lon_ref = tags.get("GPS GPSLongitudeRef")

        if None in (lat, lat_ref, lon, lon_ref):
            return None

        return convert_gps(lat, lat_ref, lon, lon_ref)


def convert_gps(lat, lat_ref, lon, lon_ref):
    """Convert GPS coordinates from EXIF to decimal degrees."""
    def to_degrees(value):
        d, m, s = [float(x.num) / float(x.den) for x in value.values]
        return d + (m / 60.0) + (s / 3600.0)

    lat = to_degrees(lat)
    if lat_ref.values[0] in ['S', 's']:
        lat = -lat

    lon = to_degrees(lon)
    if lon_ref.values[0] in ['W', 'w']:
        lon = -lon

    return lat, lon


def get_location_name(lat, lon):
    """Get a simplified location name (village and country) from GPS coordinates."""
    try:
        geolocator = Nominatim(user_agent="photo-gallery-generator")
        location = geolocator.reverse((lat, lon), exactly_one=True, language="en")
        if not location:
            return "Unknown Location"
        
        # Extract relevant components from the address
        address = location.raw.get("address", {})
        village = address.get("village") or address.get("hamlet") or address.get("town") or address.get("city")
        country = address.get("country")

        if village and country:
            return f"{village}, {country}"
        elif country:
            return country
        else:
            return "Somewhere"
    except GeopyError as e:
        print(f"Error fetching location name: {e}")
        return "Somewhere"



def create_thumbnail(image_path, thumbnail_path):
    """Create a thumbnail for the image."""
    try:
        image = Image.open(image_path)
        image.thumbnail(thumbnail_size)
        os.makedirs(os.path.dirname(thumbnail_path), exist_ok=True)
        image.save(thumbnail_path)
        return True
    except Exception as e:
        print(f"Error creating thumbnail for {image_path}: {e}")
        return False


def generate_markdown(photos_folder, thumbnail_folder, output_file, image_base_url):
    photo_entries = []
    preamble = import_preamble(preamble_f)

    for file_name in os.listdir(photos_folder):
        if file_name.lower().endswith((".png", ".jpg", ".jpeg", ".gif")):
            image_path = os.path.join(photos_folder, file_name)
            thumbnail_path = os.path.join(thumbnail_folder, file_name)
            exif = get_exif_data(image_path)
            date = get_exif_date_time(exif)
            gps_info = get_gps_info(image_path)

            if gps_info:
                lat, lon = gps_info
                location_name = get_location_name(lat, lon)
            else:
                location_name = "Unknown Location"

            # Create thumbnail
            thumbnail_url = None
            if create_thumbnail(image_path, thumbnail_path):
                thumbnail_url = f"{image_base_url}thumbnails/{file_name}"
            else:
                thumbnail_url = f"{image_base_url}{file_name}"

            photo_entries.append({
                "file_name": file_name,
                "date": date,
                "location": location_name,
                "thumbnail_url": thumbnail_url,
                "image_url": f"{image_base_url}{file_name}",
            })

    # Sort photos by date (latest first)
    photo_entries.sort(key=lambda x: x["date"] or datetime.min, reverse=True)


    # Generate markdown
    with open(output_file, "w") as md_file:
        md_file.write(f"{preamble}\n\n")
        
        for entry in photo_entries:
            file_name = entry["file_name"]
            date = entry["date"].strftime("%d %B %Y") if entry["date"] else "Sometime"
            location = entry["location"]
            thumbnail_url = entry["thumbnail_url"]
            image_url = entry["image_url"]

            md_file.write(f'<div align="center"><i> {date}, {location} </i></div>')
            md_file.write(f'<a href="{image_url}" target="_blank">\n')
            md_file.write(f'    <img src="{thumbnail_url}" alt="{file_name}" style="max-width: 200px; height: auto;">\n')
            md_file.write(f"</a>\n\n")


if __name__ == "__main__":
    generate_markdown(photos_folder, thumbnail_folder, output_file, image_base_url)
    print(f"Markdown file generated: {output_file}")
