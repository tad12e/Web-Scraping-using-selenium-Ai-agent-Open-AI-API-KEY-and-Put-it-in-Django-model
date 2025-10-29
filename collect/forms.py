from django import forms
from .models import (
    Article,
    CATEGORY_CHOICES,
    ETHIOPIAN_CATEGORY_CHOICES,
    ETHIOPIAN_REGIONS,
)


def _region_choices():
    # Convert slugs to readable labels, e.g., "addis_ababa" -> "Addis Ababa"
    return [(r, r.replace("_", " ").title()) for r in ETHIOPIAN_REGIONS]


class ArticleForm(forms.ModelForm):
    # Override regions JSONField with a MultipleChoiceField in the form
    regions = forms.MultipleChoiceField(
        choices=_region_choices(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Select all applicable regions",
    )

    # Provide nicer widgets for content and published_at
    content = forms.CharField(widget=forms.Textarea(attrs={"rows": 10}))
    published_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )

    # Let users optionally provide structured metadata
    metadata = forms.JSONField(required=False, widget=forms.Textarea(attrs={"rows": 4}))

    class Meta:
        model = Article
        fields = [
            "source_name",
            "source_url",
            "url",
            "title",
            "author",
            "published_at",
            "content",
            "category",
            "category_explanation",
            "ethiopian_category",
            "regions",
            "metadata",
        ]
        widgets = {
            "category": forms.Select(choices=CATEGORY_CHOICES),
            "ethiopian_category": forms.Select(choices=ETHIOPIAN_CATEGORY_CHOICES),
            "title": forms.TextInput(attrs={"maxlength": 500}),
            "author": forms.TextInput(attrs={"maxlength": 200}),
            "source_name": forms.TextInput(attrs={"maxlength": 200}),
        }

    def clean_regions(self):
        regions = self.cleaned_data.get("regions") or []
        # De-duplicate while preserving order
        seen = set()
        unique = []
        for r in regions:
            if r not in seen:
                seen.add(r)
                unique.append(r)
        return unique


class FeedFilterForm(forms.Form):
    """Lightweight filter form for the feed page."""
    category = forms.ChoiceField(
        choices=[("", "All")] + CATEGORY_CHOICES, required=False
    )
    ethiopian_category = forms.ChoiceField(
        choices=[("", "All")] + ETHIOPIAN_CATEGORY_CHOICES, required=False
    )
    regions = forms.MultipleChoiceField(
        choices=_region_choices(), required=False, widget=forms.CheckboxSelectMultiple
    )
