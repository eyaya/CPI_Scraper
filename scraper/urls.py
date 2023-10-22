from django.urls import path

from .views import (
    home_view,
    CountryListView,
    country_detail_view,
    #CountryDetailView
    )

app_name = 'scraper' 

urlpatterns = [ 
               path('', home_view, name='home'),
               path('countries/', CountryListView.as_view(), name='list'),
               #path('country/<pk>/', CountryDetailView.as_view(), name='detail'),
               path('country/<pk>/', country_detail_view, name='detail')
]
