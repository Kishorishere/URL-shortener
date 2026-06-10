import csv
import io
import logging

from django.core.validators import URLValidator
from django.core.exceptions import ValidationError

from shortener.models import ShortenedURL
from shortener.services.shortcode import generate_short_code

logger = logging.getLogger(__name__)


def process_bulk_csv(user, file_obj) -> tuple[list, list]:
    successes = []
    errors = []
    validator = URLValidator()

    decoded = file_obj.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(decoded))

    if "url" not in (reader.fieldnames or []):
        raise ValueError("CSV must have a 'url' column header")

    for row in reader:
        original = row.get("url", "").strip()
        if not original:
            continue
        try:
            validator(original)
            code = generate_short_code()
            ShortenedURL.objects.create(
                user=user,
                original_url=original,
                short_code=code,
            )
            successes.append({"original": original, "short_code": code})
        except ValidationError as e:
            errors.append({"original": original, "error": "Invalid URL"})
            logger.warning("Bulk CSV invalid URL: %s - %s", original, e)
        except Exception as e:
            errors.append({"original": original, "error": str(e)})
            logger.error("Bulk CSV error for %s: %s", original, e)

    return successes, errors
