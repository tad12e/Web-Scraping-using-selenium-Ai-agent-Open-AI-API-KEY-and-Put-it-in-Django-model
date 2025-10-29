from django.shortcuts import render, redirect
from .forms import ArticleForm, FeedFilterForm
from .models import Article


# Optional: simple alias view that just shows the feed
def news_view(request):
    return feed_view(request)



    
                

            


def collect_view(request):
    """Create an article manually using ArticleForm (optional)."""
    if request.method == 'POST':
        form = ArticleForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('feed')  # ensure you have a URL named 'feed'
    else:
        form = ArticleForm()
    return render(request, 'collect/collect.html', {'form': form})


def feed_view(request):
    """Show a filterable feed, latest articles first."""
    form = FeedFilterForm(request.GET or None)
    qs = Article.objects.all()

    if form.is_valid():
        category = form.cleaned_data.get("category")
        et_cat = form.cleaned_data.get("ethiopian_category")
        regions = form.cleaned_data.get("regions") or []

        if category:
            qs = qs.filter(category=category)
        if et_cat:
            qs = qs.filter(ethiopian_category=et_cat)
        if regions:
            # Match any of the selected regions
            from django.db.models import Q
            from functools import reduce
            from operator import or_ as OR
            region_q = reduce(OR, [Q(regions__contains=[r]) for r in regions])
            qs = qs.filter(region_q)

    # Order latest first; if published_at is null, fetched_at ensures sensible order
    qs = qs.order_by('-published_at', '-fetched_at')

    return render(request, 'collect/Feed.html', {"form": form, "articles": qs})