__author__ = 'Philipp Lang'

from braces.views import LoginRequiredMixin

from collections import OrderedDict

from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.forms.formsets import formset_factory
from django.views.generic.list import ListView
from django.views.generic.detail import DetailView

from dingos.models import FactTerm, InfoObject
from dingos.core.utilities import set_dict
from dingos.view_classes import ViewMethodMixin
from . import MANTIS_MALTE_TEMPLATE_FAMILY
from .forms import FactTermCorrelationEditForm
from .models import FactTermWeight, FactTerm2Weight
from .correlation_search import get_matching_io2fvs



class FactTermWeightEdit(LoginRequiredMixin, ViewMethodMixin, ListView):
    model = FactTerm

    template_name = 'mantis_malte/%s/edits/FactTermWeightEdit.html' % MANTIS_MALTE_TEMPLATE_FAMILY

    form_class = formset_factory(FactTermCorrelationEditForm, extra=0)
    formset = None

    #TODO set title
    title = 'Title Test'

    def get_context_data(self, **kwargs):
        context = super(FactTermWeightEdit, self).get_context_data(**kwargs)
        context['form'] = FactTermCorrelationEditForm()
        context['factterms'] = self.fact_terms
        context['paginator'] = self.factterms_paginator
        context['page_obj'] = self.factterms
        print "###########"
        print self.formset
        return context

    def get(self, request, *args, **kwargs):
        initial = []
        self.page = request.GET.get('page')

        columns = ['id','term','attribute','factterm_set2__assignment_name__name','factterm_set2__weight']

        factterm_list = self.get_queryset().values(*columns).order_by('term')
        self.factterms_paginator = Paginator(factterm_list, 20)

        if self.factterms_paginator.num_pages == 1:
            self.is_paginated = False
        else:
            self.is_paginated = True

        try:
            self.factterms = self.factterms_paginator.page(self.page)
        except PageNotAnInteger:
            # If page is not an integer, deliver first page.
            self.factterms = self.factterms_paginator.page(1)
        except EmptyPage:
            # If page is out of range, deliver last page of results.
            self.factterms = self.factterms_paginator.page(self.factterms_paginator.num_pages)

        self.fact_terms = OrderedDict()
        for fact_term in self.factterms:
            curr_factterm = self.fact_terms.get(fact_term['id'],False)
            if curr_factterm:
                curr_factterm['weights'].append("%s: %s" % (fact_term['factterm_set2__assignment_name__name'],fact_term['factterm_set2__weight']))
            else:
                self.fact_terms[fact_term['id']] = {
                'term' : "%s@%s" % (fact_term['term'], fact_term['attribute']) if fact_term['attribute'] else "%s" % (fact_term['term']),
                'weights' : ["%s: %s" % (fact_term['factterm_set2__assignment_name__name'],fact_term['factterm_set2__weight'])]
                }

        return super(FactTermWeightEdit, self).get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        print("Entering POST METHOD")
        print request
        self.formset = self.form_class(request.POST.dict())
        print self.formset.is_valid()
        if self.formset.is_valid() and request.user.is_authenticated() and False:
            #retrieving factterms
            factterm_qs = self.get_queryset()
            factterms = {}
            for factterm in factterm_qs:
                factterms[(factterm.term,factterm.attribute)] = factterm

            #retrieving facttermweights
            #facttermweights_qs = FactTermWeight.objects.select_related('fact_term')
            facttermweights_qs = FactTerm2Weight.objects.select_related('fact_term')
            facttermweights = {}
            for facttermweight in facttermweights_qs:
                facttermweights[(facttermweight.fact_term.pk,facttermweight.assignment_name.pk)] = facttermweight

            for form in self.formset:
                attr_list = form.cleaned_data['fact_term'].split('@')
                assert len(attr_list) > 0 and len(attr_list) < 3, "fact_term not valid"
                if len(attr_list) == 1:
                        factterm = factterms[(attr_list[0],u'')]
                else:
                    factterm = factterms[(attr_list[0],attr_list[1])]
                weight = form.cleaned_data['weight']

                if factterm:
                    if weight:
                        try:
                            facttermweight = facttermweights[factterm.pk]
                            if weight != facttermweight.weight:
                                facttermweight.weight = weight
                                facttermweight.save()
                        except KeyError:
                            facttermweight_new = FactTermWeight(fact_term=factterm,
                                                                weight=weight)
                            facttermweight_new.save()
                    else:
                        try:
                            facttermweight = facttermweights[factterm.pk]
                            facttermweight.delete()
                        except KeyError:
                            continue
        return self.get(request, *args, **kwargs)

class InfoObjectCorrelationView(LoginRequiredMixin, DetailView):
    #TODO list view with correlation
    model = InfoObject
    template_name = 'mantis_malte/%s/details/InfoObjectCorrelation.html' % MANTIS_MALTE_TEMPLATE_FAMILY
    threshold = 0.5

    def get_context_data(self, **kwargs):
        context = super(InfoObjectCorrelationView, self).get_context_data(**kwargs)
        pks = [self.get_object().pk]
        io2fvs_of_interest, matching_io2fvs = get_matching_io2fvs(pks=pks,threshold=self.threshold)

        self.matching_io2fvs = matching_io2fvs


        context['matching_io2fvs'] = self.matching_io2fvs

        fact2io2vf_oi ={}


        for io2fv in io2fvs_of_interest:
            # The set_dict function is a concise notation for
            # inserting stuff into a hierarchical dictionary.
            # The call below takes the fact2io2fvs_oi dictionary
            # and appends each io2fv to a list of io2fvs
            # associated with the pk of the contained fact_id (if the key fact_id
            # does not exist already, a singleton list is created
            # automatically.

            # In the view, we can use this dictionary to
            # get information about the objects_of_interest

            set_dict(fact2io2vf_oi,io2fv,'append',io2fv.fact_id)





        for matching_io2fv in matching_io2fvs:
            matching_io2fv.objects_oi = fact2io2vf_oi[matching_io2fv.fact_id]


        # We need to set the object_list in order for the
        # template tag 'reachable_packages' to work

        context['object_list'] = [x.iobject_id for x in context['matching_io2fvs']]

        return context


