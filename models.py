# -*- coding: utf-8 -*-

import operator

from django.db import models
from django.utils.translation import ugettext_lazy as _


class Bijection(dict):
    """A dict class that check unicity of keys and values"""
    def __init__(self):
        super(Bijection, self).__init__(self)
        self.reverse = set()

    def __setitem__(self, key, value):
        if key in self:
            raise ValueError("Duplicate key")
        if value in self.reverse:
            raise ValueError("Duplicate value")
        super(Bijection, self).__setitem__(key, value)


class ProxyOptions(object):
    def __init__(self, field, value, queryset_filter):
        self.field = field
        self.value = value
        self.queryset_filter = queryset_filter


class NonProxyOptions(object):
    def __init__(self, field, arg_rank):
        self.field = field
        self.arg_rank = arg_rank
        self.proxy_map = Bijection()


def get_non_proxy_parent(cls):
    for parent in cls.__mro__:
        if issubclass(parent, models.Model) and not parent._meta.proxy:
            return parent


class ProxyFilterModelMetaclass(models.Model.__class__):
    def __new__(cls, *args):
        new_class = super(ProxyFilterModelMetaclass, cls).__new__(cls, *args)
        if not new_class._meta.abstract and hasattr(new_class, 'Proxy'):
            proxy = new_class.Proxy
            if new_class._meta.proxy:
                parent = get_non_proxy_parent(new_class)
                field = parent._non_proxy.field
                value = proxy.value
                queryset_filter = {field: value}
                new_class._proxy = ProxyOptions(field, value, queryset_filter)
                parent._non_proxy.proxy_map[value] = new_class
                name = new_class._meta.verbose_name
                parent._meta.fields[new_class._non_proxy.arg_rank]._choices.append((value, name))
            else:
                field = proxy.field
                rank = map(operator.attrgetter('name'), new_class._meta.fields).index(field)
                new_class._non_proxy = NonProxyOptions(field, rank)
                new_class._meta.fields[rank]._choices = []
        return new_class


class ProxyFilterManager(models.Manager):
    def get_query_set(self):
        qs = super(ProxyFilterManager, self).get_query_set()
        model = self.model
        if model._meta.proxy:
            return qs.filter(**model._proxy.queryset_filter)
        return qs


class ProxyFilterModel(models.Model):
    __metaclass__ = ProxyFilterModelMetaclass

    @staticmethod
    def __new__(cls, *args, **kwargs):
        if not cls._meta.proxy:
            if len(args) > cls._non_proxy.arg_rank:
                sub_class_value = args[cls._non_proxy.arg_rank]
            else:
                try:
                    sub_class_value = kwargs[cls._non_proxy.field]
                except KeyError:
                    return models.Model.__new__(cls, *args, **kwargs)
            sub_class = cls._non_proxy.proxy_map[sub_class_value]
            return sub_class.__new__(sub_class, *args, **kwargs)
        return models.Model.__new__(cls, *args, **kwargs)

    objects = ProxyFilterManager()

    def __init__(self, *args, **kwargs):
        super(ProxyFilterModel, self).__init__(*args, **kwargs)
        if self._meta.proxy and not getattr(self, self._proxy.field):
            setattr(self, self._proxy.field, self._proxy.value)

    class Meta:
        abstract = True


class Animal(ProxyFilterModel):
    # the attribute 'choices' is reseted in the metaclass, but we use this trick
    # for Django to create the get_FIELD_display method
    species = models.CharField("Species", max_length=100, choices=True)
    name = models.CharField(max_length=100)

    class Proxy:
        field = 'species'

    def __unicode__(self):
        return '{} the {}'.format(self.name, self.get_species_display())

    def sing(self):
        raise NotImplementedError


class Cat(Animal):
    class Meta:
        proxy = True
        verbose_name = _('Kitten')

    class Proxy:
        value = 'cat'

    def sing(self):
        return 'Miaou !'


class Dog(Animal):
    class Meta:
        proxy = True
        verbose_name = _('Puppy')

    class Proxy:
        value = 'dog'

    def sing(self):
        return 'Waf waf !'


class Bird(Animal):
    class Meta:
        proxy = True
        verbose_name = _('Young bird')

    class Proxy:
        value = 'bird'

    def sing(self):
        return 'Piou piou ? (it really depends on the bird)'
