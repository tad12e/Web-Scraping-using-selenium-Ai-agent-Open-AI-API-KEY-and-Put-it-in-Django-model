# news/collector/models.py
from django.db import models


class Source(models.Model):
    name = models.CharField(max_length=200)
    base_url = models.URLField(unique=True)
    region_default = models.CharField(max_length=100, default="Global")
    category_default = models.CharField(max_length=100, default="General")
    active = models.BooleanField(default=True)

    # selectors per website
    list_page_pattern = models.CharField(max_length=200, default="")  # e.g. "page/{page}/"
    article_link_selector = models.CharField(max_length=200, default="a[href]")
    title_selector = models.CharField(max_length=200, default="h1")
    content_selector = models.CharField(max_length=200, default="article p")
    published_at_selector = models.CharField(max_length=200, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Article(models.Model):
    source = models.ForeignKey(Source, on_delete=models.CASCADE, related_name="articles")

    title = models.CharField(max_length=300)
    content = models.TextField(blank=True)
    url = models.URLField(unique=True)  # key for "not scraped before"
    published_at = models.DateTimeField(null=True, blank=True)

    category = models.CharField(max_length=100, default="General")
    region = models.CharField(max_length=100, default="Global")

    scraped_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["source"]),
            models.Index(fields=["category"]),
            models.Index(fields=["region"]),
            models.Index(fields=["published_at"]),
        ]
        ordering = ["-published_at", "-scraped_at"]

    def __str__(self):
        return self.title
