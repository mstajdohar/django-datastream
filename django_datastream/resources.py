from __future__ import absolute_import

import datetime, time

from django.conf import urls
from django.core import urlresolvers

from tastypie import bundle, exceptions, fields, resources, utils

from datastream import api as datastream_api

from . import datastream

class InvalidGranularity(exceptions.BadRequest):
    pass

QUERY_START = 's'
QUERY_END = 'e'
QUERY_GRANULARITY = 'g'

class MetricResource(resources.Resource):
    class Meta:
        allowed_methods = ('get',)
        only_detail_fields = ('datapoints', 'datastream_uri')

    # TODO: Set help text.
    id = fields.CharField(attribute='id', null=False, blank=False, readonly=True, unique=True, help_text=None)
    downsamplers = fields.ListField(attribute='downsamplers', null=False, blank=False, readonly=True, help_text=None)
    highest_granularity = fields.CharField(attribute='highest_granularity', null=False, blank=False, readonly=True, help_text=None)
    tags = fields.ListField(attribute='tags', null=True, blank=False, readonly=False, help_text=None)

    datapoints = fields.ListField('datapoints', null=True, blank=False, readonly=True, help_text=None)

    datastream_uri = fields.CharField(null=False, blank=False, readonly=True, help_text=None)

    def get_resource_uri(self, bundle_or_obj):
        kwargs = {
            'resource_name': self._meta.resource_name,
        }

        if isinstance(bundle_or_obj, bundle.Bundle):
            kwargs['pk'] = bundle_or_obj.obj.id
        else:
            kwargs['pk'] = bundle_or_obj.id

        if self._meta.api_name is not None:
            kwargs['api_name'] = self._meta.api_name

        return self._build_reverse_url('api_dispatch_detail', kwargs=kwargs)

    def get_object_list(self, request):
        # TODO: Provide users a way to query metrics by tags
        return [datastream_api.Metric(metric) for metric in datastream.find_metrics()]

    def apply_sorting(self, obj_list, options=None):
        return obj_list

    def obj_get_list(self, request=None, **kwargs):
        return self.get_object_list(request)

    def alter_list_data_to_serialize(self, request, data):
        for obj in data['objects']:
            for field_name in self._meta.only_detail_fields:
                del obj.data[field_name]
        return data

    def alter_detail_data_to_serialize(self, request, data):
        data.data['_query_params'] = self._get_query_params(request)
        return data

    def _get_query_params(self, request):
        # TODO: Support limiting downsampled value types returned

        granularity = request.GET.get(QUERY_GRANULARITY, datastream_api.Granularity.values[-1].name.lower()[0])
        for g in datastream_api.Granularity.values:
            if granularity == g.name.lower()[0]:
                granularity = g
                break
        else:
            raise InvalidGranularity("Invalid granularity: '%s'" % granularity)

        start = datetime.datetime.utcfromtimestamp(request.GET.get(QUERY_START, 0))
        end = datetime.datetime.utcfromtimestamp(request.GET.get(QUERY_END, time.time()))

        return {
            'granularity': granularity,
            'start': start,
            'end': end,
        }

    def obj_get(self, request=None, **kwargs):
        # TODO: Handle 404
        metric = datastream_api.Metric(datastream.get_tags(kwargs['pk']))

        params = self._get_query_params(request)

        metric.datapoints = datastream.get_data(kwargs['pk'], params['granularity'], params['start'], params['end'])

        return metric

    def dehydrate_datastream_uri(self, bundle):
        params = self._get_query_params(bundle.request)

        kwargs = {
            'resource_name': self._meta.resource_name,
            'pk': bundle.obj.id,
            'granularity': params['granularity'].name[0],
        }

        if self._meta.api_name is not None:
            kwargs['api_name'] = self._meta.api_name

        return urlresolvers.reverse('datastream', kwargs=kwargs)

    def override_urls(self):
        granularity = ''.join([granularity.name.lower()[0] for granularity in datastream_api.Granularity.values])
        return [
            # TODO: Define view
            urls.url(r"^(?P<resource_name>%s)/(?P<pk>\w[\w/-]*)/datastream/(?P<granularity>[%s])%s$" % (self._meta.resource_name, granularity, utils.trailing_slash()), lambda: None, name="datastream"),
        ]

    def obj_create(self, bundle, request=None, **kwargs):
        raise NotImplementedError

    def obj_update(self, bundle, request=None, **kwargs):
        raise NotImplementedError

    def obj_delete_list(self, request=None, **kwargs):
        raise NotImplementedError

    def obj_delete(self, request=None, **kwargs):
        raise NotImplementedError

    def rollback(self, bundles):
        raise NotImplementedError
