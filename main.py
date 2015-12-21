#!/usr/bin/env python

"""
main.py -- Udacity conference server-side Python App Engine
    HTTP controller handlers for memcache & task queue access

$Id$

created by wesc on 2014 may 24

Modified by Richard Gieg on 12/2/2015 for Udacity Full Stack Project #4

"""

__author__ = 'wesc+api@google.com (Wesley Chun)'

from time import sleep

import webapp2
from google.appengine.api import app_identity
from google.appengine.api import mail

from conference import ConferenceApi


class SendConfirmationEmailHandler(webapp2.RequestHandler):
    def post(self):
        """Send email confirming Conference creation."""
        mail.send_mail(
            'noreply@%s.appspotmail.com' % (
                app_identity.get_application_id()),     # from
            self.request.get('email'),                  # to
            'You created a new Conference!',            # subj
            'Hi, you have created a following '         # body
            'conference:\r\n\r\n%s' % self.request.get(
                'conferenceInfo')
        )


class SetAnnouncementHandler(webapp2.RequestHandler):
    def get(self):
        """Set Announcement in Memcache."""
        ConferenceApi._cacheAnnouncement()


class UpdateFeaturedSpeakerHandler(webapp2.RequestHandler):
    def post(self):
        """Update the featured speaker."""
        # Wait for eventual consistency to catch up, since new session was
        # just added. Since this is running on a task queue thread the wait
        # doesn't affect application responsiveness whatsoever.
        sleep(3)
        # Call the routine that performs the logic for updating the featured
        # speaker.
        ConferenceApi._updateFeaturedSpeaker(
            self.request.get('websafeSpeakerKey'),
            self.request.get('websafeConferenceKey')
        )


app = webapp2.WSGIApplication([
    ('/crons/set_announcement', SetAnnouncementHandler),
    ('/tasks/update_featured_speaker', UpdateFeaturedSpeakerHandler),
    ('/tasks/send_confirmation_email', SendConfirmationEmailHandler),
], debug=True)
