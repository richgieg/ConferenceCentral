#!/usr/bin/env python

"""
conference.py -- Udacity conference server-side Python App Engine API;
    uses Google Cloud Endpoints

$Id: conference.py,v 1.25 2014/05/24 23:42:19 wesc Exp wesc $

created by wesc on 2014 apr 21

Modified by Richard Gieg on 2015/12/20 for Udacity Full Stack Project #4

"""

__author__ = 'wesc+api@google.com (Wesley Chun)'

from datetime import datetime

import endpoints
from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb
from protorpc import messages
from protorpc import message_types
from protorpc import remote

from models import BooleanMessage
from models import CONF_DEFAULTS
from models import CONF_GET_REQUEST
from models import CONF_POST_REQUEST
from models import Conference
from models import ConferenceForm
from models import ConferenceForms
from models import ConferenceQueryForm
from models import ConferenceQueryForms
from models import ConflictException
from models import Profile
from models import ProfileMiniForm
from models import ProfileForm
from models import Session
from models import SESSION_DEFAULTS
from models import SESSION_POST_REQUEST
from models import SESSION_SPEAKER_GET_REQUEST
from models import SESSIONTYPE_GET_REQUEST
from models import SessionForm
from models import SessionForms
from models import SessionType
from models import Speaker
from models import SPEAKER_DEFAULTS
from models import SPEAKER_GET_REQUEST
from models import SpeakerForm
from models import StringMessage
from models import TeeShirtSize
from settings import WEB_CLIENT_ID


API_EXPLORER_CLIENT_ID = endpoints.API_EXPLORER_CLIENT_ID
EMAIL_SCOPE = endpoints.EMAIL_SCOPE
MEMCACHE_ANNOUNCEMENTS_KEY = "RECENT_ANNOUNCEMENTS"

OPERATORS = {
    'EQ': '=',
    'GT': '>',
    'GTEQ': '>=',
    'LT': '<',
    'LTEQ': '<=',
    'NE': '!='
}

FIELDS = {
    'CITY': 'city',
    'TOPIC': 'topics',
    'MONTH': 'month',
    'MAX_ATTENDEES': 'maxAttendees',
}


@endpoints.api(name='conference', version='v1',
    allowed_client_ids=[WEB_CLIENT_ID, API_EXPLORER_CLIENT_ID],
    scopes=[EMAIL_SCOPE])
class ConferenceApi(remote.Service):
    """Conference API v0.1"""

###############################################################################
###         Conferences: Private Methods
###############################################################################

    @staticmethod
    def _cacheAnnouncement():
        """Create Announcement & assign to memcache; used by
        memcache cron job & putAnnouncement().
        """
        confs = Conference.query(ndb.AND(
            Conference.seatsAvailable <= 5,
            Conference.seatsAvailable > 0)
        ).fetch(projection=[Conference.name])
        if confs:
            # If there are conferences close to being sold out,
            # format announcement and set it in memcache
            announcement = '%s %s' % (
                'Last chance to attend! The following conferences '
                'are nearly sold out:',
                ', '.join(conf.name for conf in confs))
            memcache.set(MEMCACHE_ANNOUNCEMENTS_KEY, announcement)
        else:
            # If there are no sold out conferences,
            # delete the memcache announcements entry
            announcement = ""
            memcache.delete(MEMCACHE_ANNOUNCEMENTS_KEY)
        return announcement

    @ndb.transactional(xg=True)
    def _conferenceRegistration(self, request, reg=True):
        """Register or unregister user for selected conference."""
        retval = None
        # Get user profile
        prof = self._getProfileFromUser()
        # Check if conference given in the websafeConfKey exists
        wsck = request.websafeConferenceKey
        conf = ndb.Key(urlsafe=wsck).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' % wsck)
        # Register
        if reg:
            # Check if user already registered, otherwise add
            if wsck in prof.conferenceKeysToAttend:
                raise ConflictException(
                    "You have already registered for this conference.")
            # Check if seats available
            if conf.seatsAvailable <= 0:
                raise ConflictException(
                    "There are no seats available.")
            # Register user, deduct one seat
            prof.conferenceKeysToAttend.append(wsck)
            conf.seatsAvailable -= 1
            retval = True
        # Unregister
        else:
            # Check if user already registered
            if wsck in prof.conferenceKeysToAttend:
                # Unregister user, add back one seat
                prof.conferenceKeysToAttend.remove(wsck)
                conf.seatsAvailable += 1
                retval = True
            else:
                retval = False
        # Update the datastore and return
        prof.put()
        conf.put()
        return BooleanMessage(data=retval)

    def _copyConferenceToForm(self, conf, displayName):
        """Copy relevant fields from Conference to ConferenceForm."""
        cf = ConferenceForm()
        for field in cf.all_fields():
            if hasattr(conf, field.name):
                # Convert Date to date string; just copy others
                if field.name.endswith('Date'):
                    setattr(cf, field.name, str(getattr(conf, field.name)))
                else:
                    setattr(cf, field.name, getattr(conf, field.name))
            elif field.name == "websafeKey":
                setattr(cf, field.name, conf.key.urlsafe())
        if displayName:
            setattr(cf, 'organizerDisplayName', displayName)
        cf.check_initialized()
        return cf

    def _createConferenceObject(self, request):
        """Create or update a conference, returning ConferenceForm/request."""
        # Preload necessary data items
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = user.email()
        if not request.name:
            raise endpoints.BadRequestException(
                "Conference 'name' field required")
        # Copy ConferenceForm/ProtoRPC Message into dict
        data = {
            field.name: getattr(request, field.name) for field in
                request.all_fields()
        }
        del data['websafeKey']
        del data['organizerDisplayName']
        # Add default values for those missing (both data model and
        # outbound Message)
        for df in CONF_DEFAULTS:
            if data[df] in (None, []):
                data[df] = CONF_DEFAULTS[df]
                setattr(request, df, CONF_DEFAULTS[df])
        # Convert dates from strings to Date objects; set month based
        # on start_date
        if data['startDate']:
            data['startDate'] = datetime.strptime(
                data['startDate'][:10], "%Y-%m-%d").date()
            data['month'] = data['startDate'].month
        else:
            data['month'] = 0
        if data['endDate']:
            data['endDate'] = datetime.strptime(
                data['endDate'][:10], "%Y-%m-%d").date()
        # Set seatsAvailable to be same as maxAttendees on creation
        if data["maxAttendees"] > 0:
            data["seatsAvailable"] = data["maxAttendees"]
        # Get the user profile key, then set the conference's parent
        # to that value.
        # NOTE: The original code made a call to allocate_ids in order to
        #       generate an ID for the conference. Since the profiles utilize
        #       strings (email addresses) for their IDs, resulting in no risk
        #       of colliding with NDB's auto-generated numeric IDs, I decided
        #       to let NDB generate the conference ID automatically.
        # https://cloud.google.com/appengine/docs/python/ndb/entities?hl=en#numeric_keys
        p_key = ndb.Key(Profile, user_id)
        data['parent'] = p_key
        data['organizerUserId'] = request.organizerUserId = user_id
        # Create Conference, send email to organizer confirming
        # creation of Conference and return (modified) ConferenceForm
        Conference(**data).put()
        taskqueue.add(params={'email': user.email(),
            'conferenceInfo': repr(request)},
            url='/tasks/send_confirmation_email'
        )
        return request

    def _formatFilters(self, filters):
        """Parse, check validity and format user supplied filters."""
        formatted_filters = []
        inequality_field = None
        for f in filters:
            filtr = {
                field.name: getattr(f, field.name) for field in f.all_fields()
            }
            try:
                filtr["field"] = FIELDS[filtr["field"]]
                filtr["operator"] = OPERATORS[filtr["operator"]]
            except KeyError:
                raise endpoints.BadRequestException(
                    "Filter contains invalid field or operator.")
            # Every operation except "=" is an inequality
            if filtr["operator"] != "=":
                # Check if inequality operation has been used in previous
                # filters disallow the filter if inequality was performed on a
                # different field before. Track the field on which the
                # inequality operation is performed.
                if inequality_field and inequality_field != filtr["field"]:
                    raise endpoints.BadRequestException(
                        "Inequality filter is allowed on only one field.")
                else:
                    inequality_field = filtr["field"]
            formatted_filters.append(filtr)
        return (inequality_field, formatted_filters)

    def _getQuery(self, request):
        """Return formatted query from the submitted filters."""
        q = Conference.query()
        inequality_filter, filters = self._formatFilters(request.filters)
        # If exists, sort on inequality filter first
        if not inequality_filter:
            q = q.order(Conference.name)
        else:
            q = q.order(ndb.GenericProperty(inequality_filter))
            q = q.order(Conference.name)
        for filtr in filters:
            if filtr["field"] in ["month", "maxAttendees"]:
                try:
                    filtr["value"] = int(filtr["value"])
                except ValueError:
                    raise endpoints.BadRequestException(
                        "Non-integer in integer field.")
            formatted_query = ndb.query.FilterNode(
                filtr["field"], filtr["operator"], filtr["value"])
            q = q.filter(formatted_query)
        return q

    @ndb.transactional()
    def _updateConferenceObject(self, request):
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = user.email()
        # Copy ConferenceForm/ProtoRPC Message into dict
        data = {
            field.name: getattr(request, field.name) for field in
                request.all_fields()
        }
        # Update existing conference
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        # Check that conference exists
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' %
                    request.websafeConferenceKey
            )
        # Check that user is owner
        if user_id != conf.organizerUserId:
            raise endpoints.ForbiddenException(
                'Only the owner can update the conference.')
        # Not getting all the fields, so don't create a new object; just
        # copy relevant fields from ConferenceForm to Conference object
        for field in request.all_fields():
            data = getattr(request, field.name)
            # Only copy fields where we get data
            if data not in (None, []):
                # Special handling for dates (convert string to Date)
                if field.name in ('startDate', 'endDate'):
                    data = datetime.strptime(data, "%Y-%m-%d").date()
                    if field.name == 'startDate':
                        conf.month = data.month
                # Write to Conference object
                setattr(conf, field.name, data)
        conf.put()
        prof = ndb.Key(Profile, user_id).get()
        return self._copyConferenceToForm(conf, getattr(prof, 'displayName'))

###############################################################################
###         Conferences: Endpoints Methods
###############################################################################

    @endpoints.method(ConferenceForm, ConferenceForm, path='conference',
            http_method='POST', name='createConference')
    def createConference(self, request):
        """Create new conference."""
        return self._createConferenceObject(request)

    @endpoints.method(message_types.VoidMessage, StringMessage,
            path='conference/announcement/get',
            http_method='GET', name='getAnnouncement')
    def getAnnouncement(self, request):
        """Return Announcement from memcache."""
        announcement = memcache.get(MEMCACHE_ANNOUNCEMENTS_KEY) or ""
        return StringMessage(data=announcement)

    @endpoints.method(CONF_GET_REQUEST, ConferenceForm,
            path='conference/{websafeConferenceKey}',
            http_method='GET', name='getConference')
    def getConference(self, request):
        """Return requested conference (by websafeConferenceKey)."""
        # Get Conference object from request; bail if not found
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' %
                    request.websafeConferenceKey
            )
        prof = conf.key.parent().get()
        # Return ConferenceForm
        return self._copyConferenceToForm(conf, getattr(prof, 'displayName'))

    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='getConferencesCreated',
            http_method='POST', name='getConferencesCreated')
    def getConferencesCreated(self, request):
        """Return conferences created by user."""
        # Make sure user is authenticated
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = user.email()
        # Create ancestor query for all key matches for this user
        confs = Conference.query(ancestor=ndb.Key(Profile, user_id))
        prof = ndb.Key(Profile, user_id).get()
        # Return set of ConferenceForm objects per Conference
        return ConferenceForms(
            items=[
                self._copyConferenceToForm(
                    conf, getattr(prof, 'displayName')) for conf in confs
            ]
        )

    @endpoints.method(message_types.VoidMessage, ConferenceForms,
            path='conferences/attending',
            http_method='GET', name='getConferencesToAttend')
    def getConferencesToAttend(self, request):
        """Get list of conferences for which the user has registered."""
        prof = self._getProfileFromUser() # get user Profile
        conf_keys = [
            ndb.Key(urlsafe=wsck) for wsck in prof.conferenceKeysToAttend
        ]
        conferences = ndb.get_multi(conf_keys)
        # Get organizers
        organisers = [
            ndb.Key(Profile, conf.organizerUserId) for conf in conferences
        ]
        profiles = ndb.get_multi(organisers)
        # Put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName
        # Return set of ConferenceForm objects per Conference
        return ConferenceForms(
            items=[
                self._copyConferenceToForm(conf, names[conf.organizerUserId])
                    for conf in conferences
            ]
        )

    @endpoints.method(ConferenceQueryForms, ConferenceForms,
            path='queryConferences',
            http_method='POST',
            name='queryConferences')
    def queryConferences(self, request):
        """Query for conferences."""
        conferences = self._getQuery(request)
        # Need to fetch organiser displayName from profiles
        # Get all keys and use get_multi for speed
        organisers = [
            (ndb.Key(Profile, conf.organizerUserId)) for conf in conferences
        ]
        profiles = ndb.get_multi(organisers)
        # Put display names in a dict for easier fetching
        names = {}
        for profile in profiles:
            names[profile.key.id()] = profile.displayName
        # Return individual ConferenceForm object per Conference
        return ConferenceForms(
            items=[
                self._copyConferenceToForm(conf, names[conf.organizerUserId])
                    for conf in conferences
            ]
        )

    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
            path='conference/{websafeConferenceKey}',
            http_method='POST', name='registerForConference')
    def registerForConference(self, request):
        """Register user for selected conference."""
        return self._conferenceRegistration(request)

    @endpoints.method(CONF_GET_REQUEST, BooleanMessage,
            path='conference/{websafeConferenceKey}',
            http_method='DELETE', name='unregisterFromConference')
    def unregisterFromConference(self, request):
        """Unregister user for selected conference."""
        return self._conferenceRegistration(request, reg=False)

    @endpoints.method(CONF_POST_REQUEST, ConferenceForm,
            path='conference/{websafeConferenceKey}',
            http_method='PUT', name='updateConference')
    def updateConference(self, request):
        """Update conference with provided fields and return updated info."""
        return self._updateConferenceObject(request)

###############################################################################
###         Speakers: Private Methods
###############################################################################

    def _copySpeakerToForm(self, speaker):
        """Copy relevant fields from Speaker to SpeakerForm."""
        sf = SpeakerForm()
        for field in sf.all_fields():
            if hasattr(speaker, field.name):
                setattr(sf, field.name, getattr(speaker, field.name))
            elif field.name == "websafeKey":
                setattr(sf, field.name, speaker.key.urlsafe())
        sf.check_initialized()
        return sf

    def _createSpeakerObject(self, request):
        """Create a speaker, returning SpeakerForm/request."""
        # Preload necessary data items
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = user.email()
        if not request.name:
            raise endpoints.BadRequestException(
                "Speaker 'name' field required")
        # Copy SpeakerForm/ProtoRPC Message into dict
        data = {
            field.name: getattr(request, field.name) for field in
                request.all_fields()
        }
        del data['websafeKey']
        # Add default values for those missing (both data model and
        # outbound Message)
        for df in SPEAKER_DEFAULTS:
            if data[df] in (None, []):
                data[df] = SPEAKER_DEFAULTS[df]
                setattr(request, df, SPEAKER_DEFAULTS[df])
        # Create Speaker and return SpeakerForm
        Speaker(**data).put()
        return request

###############################################################################
###         Speakers: Endpoints Methods
###############################################################################

    @endpoints.method(SpeakerForm, SpeakerForm, path='speaker',
            http_method='POST', name='createSpeaker')
    def createSpeaker(self, request):
        """Create new speaker."""
        return self._createSpeakerObject(request)

    @endpoints.method(SPEAKER_GET_REQUEST, SpeakerForm, path='speaker',
            http_method='GET', name='getSpeaker')
    def getSpeaker(self, request):
        """Return requested speaker (by websafeConferenceKey)."""
        # Get Speaker object from request; bail if not found
        speaker = ndb.Key(urlsafe=request.websafeSpeakerKey).get()
        if not speaker:
            raise endpoints.NotFoundException(
                'No speaker found with key: %s' %
                    request.websafeConferenceKey
            )
        # Return SpeakerForm
        return self._copySpeakerToForm(speaker)

###############################################################################
###         Sessions: Private Methods
###############################################################################

    @ndb.transactional(xg=True)
    def _createSessionObject(self, request):
        """Create a session, returning SessionForm/request."""
        # Preload necessary data items
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        user_id = user.email()
        # Get the conference object
        conf = ndb.Key(urlsafe=request.websafeConferenceKey).get()
        if not conf:
            raise endpoints.NotFoundException(
                'No conference found with key: %s' %
                    request.websafeConferenceKey
                )
        # Ensure that the current user is the conference organizer
        if user_id != conf.organizerUserId:
            raise endpoints.UnauthorizedException(
                'Only the conference organize can create a new session')
        # Ensure that the user submitted the required speaker property
        if not request.speakerWebsafeKey:
            raise endpoints.BadRequestException(
                "Session 'speakerWebsafeKey' field required")
        # Get the speaker object
        speaker = ndb.Key(urlsafe=request.speakerWebsafeKey).get()
        if not speaker:
            raise endpoints.NotFoundException(
                'No speaker found with key: %s' %
                    request.speakerWebsafeKey
                )
        # Ensure that the user submitted the required name property
        if not request.name:
            raise endpoints.BadRequestException(
                "Session 'name' field required")
        # Copy SessionForm/ProtoRPC Message into dict
        data = {
            field.name: getattr(request, field.name) for field in
                request.all_fields()
        }
        del data['websafeConferenceKey']
        del data['websafeKey']
        # Add default values for those missing (both data model and
        # outbound Message)
        for df in SESSION_DEFAULTS:
            if data[df] in (None, []):
                data[df] = SESSION_DEFAULTS[df]
                if df == 'typeOfSession':
                    setattr(request, df,
                        getattr(SessionType, SESSION_DEFAULTS[df]))
                else:
                    setattr(request, df, SESSION_DEFAULTS[df])
        # Ensure the string version of typeOfSession is what is stored
        # in the NDB model
        data['typeOfSession'] = str(data['typeOfSession'])
        # Convert dates from strings to Date objects; set month based
        # on start_date
        if data['date']:
            data['date'] = datetime.strptime(
                data['date'][:10], "%Y-%m-%d").date()
        # Create Session and return SessionForm
        session = Session(**data)
        session.conference = conf.key
        session.put()
        return self._copySessionToForm(session)

    def _copySessionToForm(self, session):
        """Copy relevant fields from Session to SessionForm."""
        sf = SessionForm()
        for field in sf.all_fields():
            if hasattr(session, field.name):
                # Convert date field to date string
                if field.name == 'date':
                    setattr(sf, field.name, str(getattr(session, field.name)))
                elif field.name == 'typeOfSession':
                    setattr(sf, field.name,
                        getattr(SessionType, getattr(session, field.name)))
                elif field.name == "websafeKey":
                    setattr(sf, field.name, session.key.urlsafe())
                else:
                    setattr(sf, field.name, getattr(session, field.name))
        sf.check_initialized()
        return sf

    def _getConferenceSessions(self, request):
        """Retrieve all sessions associated with a conference."""
        try:
            confKey = ndb.Key(urlsafe=request.websafeConferenceKey)
        except:
            raise endpoints.BadRequestException(
                'Invalid conference key: %s' %
                    request.websafeConferenceKey
                )
        # Retrieve all sessions that have a matching conference key
        sessions = Session.query(Session.conference == confKey).fetch()
        return sessions

    def _getConferenceSessionsByType(self, request):
        """Retrieve all sessions associated with a conference, by type."""
        try:
            confKey = ndb.Key(urlsafe=request.websafeConferenceKey)
        except:
            raise endpoints.BadRequestException(
                'Invalid conference key: %s' %
                    request.websafeConferenceKey
                )
        # Retrieve all sessions that have a matching conference key, by type
        sessions = Session.query(
            Session.conference == confKey,
            Session.typeOfSession == request.typeOfSession
        ).fetch()
        return sessions

    def _getSessionsBySpeaker(self, request):
        """Retrieve all sessions given by a particular speaker."""
        try:
            speakerKey = ndb.Key(urlsafe=request.websafeSpeakerKey)
        except:
            raise endpoints.BadRequestException(
                'Invalid speaker key: %s' %
                    request.websafeSpeakerKey
                )
        # Retrieve all sessions that have a matching speaker key
        sessions = Session.query(
            Session.speakerWebsafeKey == request.websafeSpeakerKey
        ).fetch()
        return sessions

###############################################################################
###         Sessions: Endpoints Methods
###############################################################################

    @endpoints.method(SESSION_POST_REQUEST, SessionForm,
            path='conference/{websafeConferenceKey}/createsession',
            http_method='POST', name='createSession')
    def createSession(self, request):
        """Create new session."""
        return self._createSessionObject(request)

    @endpoints.method(CONF_GET_REQUEST, SessionForms,
            path='conference/{websafeConferenceKey}/sessions',
            http_method='GET',
            name='getConferenceSessions')
    def getConferenceSessions(self, request):
        """Get list of sessions associated with a conference."""
        sessions = self._getConferenceSessions(request)
        # Return individual SessionForm object per Session
        return SessionForms(
            items=[self._copySessionToForm(session) for session in sessions]
        )

    @endpoints.method(SESSIONTYPE_GET_REQUEST, SessionForms,
            path='conference/{websafeConferenceKey}/sessionsbytype',
            http_method='GET',
            name='getConferenceSessionsByType')
    def getConferenceSessionsByType(self, request):
        """Get list of sessions associated with a conference (by type)."""
        sessions = self._getConferenceSessionsByType(request)
        # Return individual SessionForm object per Session
        return SessionForms(
            items=[self._copySessionToForm(session) for session in sessions]
        )

    @endpoints.method(SESSION_SPEAKER_GET_REQUEST, SessionForms,
            path='/sessionsbyspeaker/{websafeSpeakerKey}',
            http_method='GET',
            name='getSessionsBySpeaker')
    def getSessionsBySpeaker(self, request):
        """Get list of sessions given by particular speaker."""
        sessions = self._getSessionsBySpeaker(request)
        # Return individual SessionForm object per Session
        return SessionForms(
            items=[self._copySessionToForm(session) for session in sessions]
        )

###############################################################################
###         Profiles: Private Methods
###############################################################################

    def _copyProfileToForm(self, prof):
        """Copy relevant fields from Profile to ProfileForm."""
        pf = ProfileForm()
        for field in pf.all_fields():
            if hasattr(prof, field.name):
                # Convert t-shirt string to Enum; just copy others
                if field.name == 'teeShirtSize':
                    setattr(pf, field.name,
                            getattr(TeeShirtSize, getattr(prof, field.name)))
                else:
                    setattr(pf, field.name, getattr(prof, field.name))
        pf.check_initialized()
        return pf

    def _doProfile(self, save_request=None):
        """Get Profile and return to user, possibly updating it first."""
        prof = self._getProfileFromUser()
        # If saveProfile(), process user-modifyable fields
        if save_request:
            for field in ('displayName', 'teeShirtSize'):
                if hasattr(save_request, field):
                    val = getattr(save_request, field)
                    if val:
                        print(val)
                        setattr(prof, field, str(val))
            prof.put()
        # Return ProfileForm
        return self._copyProfileToForm(prof)

    def _getProfileFromUser(self):
        """Return Profile from datastore, creating new one if non-existent."""
        # Make sure user is authenticated
        user = endpoints.get_current_user()
        if not user:
            raise endpoints.UnauthorizedException('Authorization required')
        # Get Profile from datastore
        user_id = user.email()
        p_key = ndb.Key(Profile, user_id)
        profile = p_key.get()
        # Create new Profile if not there
        if not profile:
            profile = Profile(
                key = p_key,
                displayName = user.nickname(),
                mainEmail= user.email(),
                teeShirtSize = str(TeeShirtSize.NOT_SPECIFIED),
            )
            profile.put()
        return profile

###############################################################################
###         Profiles: Endpoints Methods
###############################################################################

    @endpoints.method(message_types.VoidMessage, ProfileForm,
            path='profile', http_method='GET', name='getProfile')
    def getProfile(self, request):
        """Return user profile."""
        return self._doProfile()

    @endpoints.method(ProfileMiniForm, ProfileForm,
            path='profile', http_method='POST', name='saveProfile')
    def saveProfile(self, request):
        """Update and return user profile."""
        return self._doProfile(request)


# Create the API
api = endpoints.api_server([ConferenceApi])
