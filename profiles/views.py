from django.shortcuts import render
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from .models import Profile
# Create your views here.

class ProfileList(ListView):
    model = Profile
    template_name = 'users/profile_list.html'
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = self.request.GET.get('parameter', None)
        return ctx

    def get_queryset(self):
        title = self.request.GET.get('parameter', None)
        return Profile.objects.filter(Q(user__user_type='teacher') | Q(user__user_type="head"),user__department=title).order_by('user__first_name')



class ProfileDetailView(DetailView):
    model = Profile
    template_name = 'users/profile_detail.html'
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['title'] = self.request.GET.get('parameter', None)
        return ctx

    def get_queryset(self):
        title = self.request.GET.get('parameter', None)
        return Profile.objects.all()
