from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError

# Ethiopian-focused label set to align with collect/an.py ETHIOPIAN_CATEGORIES
CATEGORY_CHOICES = [
	("politics", "Politics"),
	("economy_business", "Economy & Business"),
	("regional_conflicts", "Regional Conflicts"),
	("agriculture", "Agriculture"),
	("infrastructure", "Infrastructure"),
	("education_health", "Education & Health"),
	("culture_tourism", "Culture & Tourism"),
	("sports", "Sports"),
	("international_relations", "International Relations"),
	("social_issues", "Social Issues"),
]

# Allowed Ethiopian regions (align with collect/an.py)
ETHIOPIAN_REGIONS = [
	"addis_ababa", "oromia", "amhara", "tigray", "snnpr", "afar",
	"somali", "benishangul_gumuz", "gambela", "sidama", "south_west",
	"dire_dawa", "harari", "multiple_regions", "national", "international",
]

def validate_regions(value):
	"""Ensure all items in regions are valid Ethiopian regions."""
	if value is None:
		return
	if not isinstance(value, (list, tuple)):
		raise ValidationError("regions must be a list of region slugs")
	invalid = [v for v in value if v not in ETHIOPIAN_REGIONS]
	if invalid:
		raise ValidationError(f"Invalid regions: {', '.join(invalid)}")


class Article(models.Model):
	"""Stores a scraped and optionally AI-classified news article."""

	# Source info
	source_name = models.CharField(max_length=200)
	source_url = models.URLField()

	# Article identity
	url = models.URLField(unique=True)
	title = models.CharField(max_length=500, blank=True)
	author = models.CharField(max_length=200, blank=True)

	# Timestamps
	published_at = models.DateTimeField(null=True, blank=True)
	fetched_at = models.DateTimeField(default=timezone.now)
	created_at = models.DateTimeField(auto_now_add=True)
	updated_at = models.DateTimeField(auto_now=True)

	# Content
	content = models.TextField()

	# Classification
	category = models.CharField(max_length=32, choices=CATEGORY_CHOICES, default="other")
	category_explanation = models.TextField(blank=True)

	# Ethiopian-specific classification outputs
	ethiopian_category = models.CharField(
		max_length=64,
		choices=CATEGORY_CHOICES,
		default="social_issues",
		blank=True,
	)
	regions = models.JSONField(
		default=list,
		blank=True,
		help_text="List of Ethiopian regions relevant to the article",
		validators=[validate_regions],
	)

	# Extra metadata
	metadata = models.JSONField(default=dict, blank=True)

	class Meta:
		indexes = [
			models.Index(fields=["url"]),
			models.Index(fields=["category"]),
			models.Index(fields=["ethiopian_category"]),
			models.Index(fields=["published_at"]),
		]
		ordering = ["-published_at", "-fetched_at"]

	def __str__(self) -> str:  # pragma: no cover
		return self.title or self.url

