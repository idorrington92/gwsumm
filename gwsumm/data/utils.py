# -*- coding: utf-8 -*-
# Copyright (C) Duncan Macleod (2013)
#
# This file is part of GWSumm.
#
# GWSumm is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# GWSumm is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GWSumm.  If not, see <http://www.gnu.org/licenses/>.

"""Utilities for data loading and pre-processing
"""

from functools import wraps

try:
    from collections import OrderedDict
except ImportError:
    from ordereddict import OrderedDict

from glue.segments import segmentlist as GlueSegmentList

from gwpy.segments import (DataQualityFlag, SegmentList, Segment)

from ..channels import get_channel
from ..config import GWSummConfigParser

__author__ = 'Duncan Macleod <duncan.macleod@ligo.org>'


# -- method decorators --------------------------------------------------------

def use_segmentlist(f):
    """Decorate a method to convert incoming segments into a `SegmentList`

    This assumes that the method to be decorated takes a segment list as
    the second positionsl argument.
    """
    @wraps(f)
    def decorated_func(arg1, segments, *args, **kwargs):
        if isinstance(segments, DataQualityFlag):
            segments = segments.active
        elif not isinstance(segments, GlueSegmentList):
            segments = SegmentList([Segment(*x) for x in segments])
        return f(arg1, segments, *args, **kwargs)
    return decorated_func


def use_configparser(f):
    """Decorate a method to use a valid default for 'config'

    This is just to allow lazy passing of `config=None`
    """
    @wraps(f)
    def decorated_func(*args, **kwargs):
        if kwargs.get('config', None) is None:
            kwargs['config'] = GWSummConfigParser()
        return f(*args, **kwargs)
    return decorated_func


# -- handle keys for globalv dicts --------------------------------------------
# need a key that is unique across channel(s) with a specific for of
# signal-processing parameters

FFT_PARAMS = OrderedDict([
    ('method', str),  # keep this one first (DMM)
    ('fftlength', float),
    ('overlap', float),
    ('window', None),
    ('stride', float),
])


class FftParams(object):
    """Convenience object to hold signal-processing parameters
    """
    __slots__ = FFT_PARAMS.keys()

    def __init__(self, **kwargs):
        for slot in self.__slots__:
            kwargs.setdefault(slot, None)
        for key in kwargs:
            setattr(self, key, kwargs[key])

    def __setattr__(self, key, val):
        if val is not None and FFT_PARAMS[key] is not None:
            val = FFT_PARAMS[key](val)
        super(FftParams, self).__setattr__(key, val)

    def __str__(self):
        return ';'.join(str(getattr(self, slot)) if getattr(self, slot) else ''
                        for slot in self.__slots__)

    def dict(self):
        return dict((x, getattr(self, x)) for x in self.__slots__)


def get_fftparams(channel, **defaults):
    channel = get_channel(channel)
    fftparams = FftParams(**defaults)
    for key in fftparams.__slots__:
        try:
            setattr(fftparams, key, getattr(channel, key))
        except AttributeError:
            try:  # set attribute in channel object for future reference
                setattr(channel, key, defaults[key])
            except KeyError:
                pass

    # set stride to something sensible
    if fftparams.stride is None and fftparams.overlap:
        fftparams.stride = fftparams.fftlength * 1.5
    elif fftparams.stride is None:
        fftparams.stride = fftparams.fftlength

    # sanity check parameters
    if fftparams.fftlength == 0:
        raise ZeroDivisionError("Cannot operate with FFT length of 0")
    if fftparams.stride == 0:
        raise ZeroDivisionError("Cannot generate spectrogram with stride "
                                "length of 0")
    return fftparams


def make_globalv_key(channels, fftparams=None):
    """Generate a unique key for storing data in a globalv `dict`

    Parameters
    ----------
    channels : `str`, `list`
        one or more channels to group in this key
    fftparams : `FftParams`
        structured set of signal-processing parameters used to generate the
        dataset
    """
    if not isinstance(channels, (list, tuple)):
        channels = [channels]
    channels = map(get_channel, channels)
    parts = []
    # comma-separated list of names
    parts.append(','.join(c.ndsname for c in channels))
    # colon-separated list of FFT parameters
    if fftparams is not None:
        parts.append(fftparams)
    return ';'.join(map(str, parts))
