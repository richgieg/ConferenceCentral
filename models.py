#!/usr/bin/env python

"""
models.py -- Udacity conference server-side Python App Engine
    data & ProtoRPC models

$Id: models.py,v 1.1 2014/05/24 22:01:10 wesc Exp $

created/forked from conferences.py by wesc on 2014 may 24

Modified by Richard Gieg on 2015/12/20 for Udacity Full Stack Project #4

"""

__author__ = 'wesc+api@google.com (Wesley Chun)'

import httplib

import endpoints
from google.appengine.ext import ndb
from protorpc import messages
from protorpc import message_types


###############################################################################
###         Models: Conferences
###############################################################################


class Conference(ndb.Model):
    """Conference object."""
    name = ndb.StringProperty(required=True)
    description = ndb.StringProperty()
    organizerUserId = ndb.StringProperty()
    topics = ndb.StringProperty(repeated=True)
    city = ndb.StringProperty()
    startDate = ndb.DateProperty()
    month = ndb.IntegerProperty()
    endDate = ndb.DateProperty()
    maxAttendees = ndb.IntegerProperty()
    seatsAvailable = ndb.IntegerProperty()
    sessions = ndb.KeyProperty(repeated=True)


class ConferenceForm(messages.Message):
    """Conference inbound/outbound form message."""
    name = messages.StringField(1)
    description = messages.StringField(2)
    organizerUserId = messages.StringField(3)
    topics = messages.StringField(4, repeated=True)
    city = messages.StringField(5)
    startDate = messages.StringField(6)
    month = messages.IntegerField(7, variant=messages.Variant.INT32)
    maxAttendees = messages.IntegerField(8, variant=messages.Variant.INT32)
    seatsAvailable = messages.IntegerField(9, variant=messages.Variant.INT32)
    endDate = messages.StringField(10)
    websafeKey = messages.StringField(11)
    organizerDisplayName = messages.StringField(12)


class ConferenceForms(messages.Message):
    """Multiple Conference outbound form message."""
    items = messages.MessageField(ConferenceForm, 1, repeated=True)


class ConferenceQueryForm(messages.Message):
    """Conference query inbound form message."""
    field = messages.StringField(1)
    operator = messages.StringField(2)
    value = messages.StringField(3)


class ConferenceQueryForms(messages.Message):
    """Multiple ConferenceQueryForm inbound form message."""
    filters = messages.MessageField(ConferenceQueryForm, 1, repeated=True)


CONF_DEFAULTS = {
    "city": "Default City",
    "maxAttendees": 0,
    "seatsAvailable": 0,
    "topics": ["Default", "Topic"],
}


CONF_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
)


CONF_POST_REQUEST = endpoints.ResourceContainer(
    ConferenceForm,
    websafeConferenceKey=messages.StringField(1),
)


###############################################################################
###         Models: Speakers
###############################################################################


class Speaker(ndb.Model):
    """Speaker object."""
    name = ndb.StringProperty(required=True)
    company = ndb.StringProperty(indexed=False)
    email = ndb.StringProperty(indexed=False)
    phone = ndb.StringProperty(indexed=False)
    websiteUrl = ndb.StringProperty(indexed=False)


class SpeakerForm(messages.Message):
    """Speaker inbound/outbound form message."""
    name = messages.StringField(1)
    company = messages.StringField(2)
    email = messages.StringField(3)
    phone = messages.StringField(4)
    websiteUrl = messages.StringField(5)
    websafeKey = messages.StringField(6)


SPEAKER_DEFAULTS = {
    "company": "Default Company",
    "email": "speaker@example.com",
    "phone": "555-555-5555",
    "websiteUrl": "http://www.example.com",
}


SPEAKER_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeSpeakerKey=messages.StringField(1),
)


###############################################################################
###         Models: Sessions
###############################################################################


class Session(ndb.Model):
    """Session object."""
    name = ndb.StringProperty(required=True)
    highlights = ndb.StringProperty(repeated=True)
    speakerWebsafeKey = ndb.StringProperty(required=True)
    duration = ndb.IntegerProperty()
    typeOfSession = ndb.StringProperty(default='NOT_SPECIFIED')
    date = ndb.DateProperty()
    startTime = ndb.StringProperty()


class SessionForm(messages.Message):
    """Session inbound/outbound form message."""
    name = messages.StringField(1)
    highlights = messages.StringField(2, repeated=True)
    speakerWebsafeKey = messages.StringField(3)
    duration = messages.IntegerField(4, variant=messages.Variant.INT32)
    typeOfSession = messages.EnumField('SessionType', 5)
    date = messages.StringField(6)
    startTime = messages.StringField(7)
    websafeKey = messages.StringField(8)


class SessionForms(messages.Message):
    """Multiple Session outbound form message."""
    items = messages.MessageField(SessionForm, 1, repeated=True)


class SessionType(messages.Enum):
    """Session type enumeration value."""
    NOT_SPECIFIED = 1
    DEMONSTRATION = 2
    LECTURE = 3
    ROUNDTABLE = 4
    WORKSHOP = 5


SESSION_DEFAULTS = {
    "highlights": ["Default", "Highlight"],
    "duration": 60,
    "startTime": "00:00",
    "typeOfSession": "NOT_SPECIFIED"
}


SESSION_POST_REQUEST = endpoints.ResourceContainer(
    SessionForm,
    websafeConferenceKey=messages.StringField(1),
)

SESSIONTYPE_GET_REQUEST = endpoints.ResourceContainer(
    message_types.VoidMessage,
    websafeConferenceKey=messages.StringField(1),
    type=messages.StringField(2),
)


###############################################################################
###         Models: Profiles
###############################################################################


class Profile(ndb.Model):
    """User profile object."""
    displayName = ndb.StringProperty()
    mainEmail = ndb.StringProperty()
    teeShirtSize = ndb.StringProperty(default='NOT_SPECIFIED')
    conferenceKeysToAttend = ndb.StringProperty(repeated=True)


class ProfileForm(messages.Message):
    """Profile outbound form message."""
    displayName = messages.StringField(1)
    mainEmail = messages.StringField(2)
    teeShirtSize = messages.EnumField('TeeShirtSize', 3)
    conferenceKeysToAttend = messages.StringField(4, repeated=True)


class ProfileMiniForm(messages.Message):
    """Update Profile form message."""
    displayName = messages.StringField(1)
    teeShirtSize = messages.EnumField('TeeShirtSize', 2)


class TeeShirtSize(messages.Enum):
    """T-shirt size enumeration value."""
    NOT_SPECIFIED = 1
    XS_M = 2
    XS_W = 3
    S_M = 4
    S_W = 5
    M_M = 6
    M_W = 7
    L_M = 8
    L_W = 9
    XL_M = 10
    XL_W = 11
    XXL_M = 12
    XXL_W = 13
    XXXL_M = 14
    XXXL_W = 15


###############################################################################
###         Models: General
###############################################################################


class BooleanMessage(messages.Message):
    """Outbound Boolean value message"""
    data = messages.BooleanField(1)


class StringMessage(messages.Message):
    """Outbound (single) string message"""
    data = messages.StringField(1, required=True)


class ConflictException(endpoints.ServiceException):
    """Exception mapped to HTTP 409 response"""
    http_status = httplib.CONFLICT
