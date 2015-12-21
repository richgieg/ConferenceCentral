# Conference Central

This is the fourth project in my pursuit of the Full Stack Web Developer
Nanodegree from Udacity. Prior to starting this project I completed the
Udacity course entitled "Developing Scalable Apps in Python". The focus
of this project is leveraging the powerful Google App Engine framework,
including Cloud Endpoints and Datastore, to develop highly-scalable
applications with APIs that are accessible from a wide variety of devices.
Following is Udacity's description for this project:

"You will develop a cloud-based API server to support a provided conference
organization application that exists on the web as well as a native Android
application. The API supports the following functionality found within the
app: user authentication, user profiles, conference information and various
manners in which to query the data."


## Accessing the Application

To access the front-end of the application, visit the following link:

https://conference-central-123.appspot.com

From the landing page you can navigate to other pages which will allow you
to view, create and register for conferences. You will be prompted to log
in with your Google account before you're actually allowed to create a
conference or register to attend a conference. Keep in mind, all conferences
on this site are fictional, so don't get your hopes up... ;)


## Accessing the API Explorer

To access the back-end of the application, visit the following link:

https://conference-central-123.appspot.com/_ah/api/explorer

From here you can select "Conference API v0.1" which will bring you to a list
of all API methods exposed by the Conference Central application. This allows
you to experiment directly with the functions that the front-end utilizes
behind the scenes to do the "heavy lifting". Just as some features of the
front-end require authentication, many API methods require you to be
authenticated as well. For example, click on the `conference.getProfile` API.
You should see a button that says, "Authorize and Execute". Click the button,
sign in with your Google account, then observe the JSON information returned.
You should your email address, display name, etc. Feel free to play around
with the other API methods. Keep in mind, some require input from you in
order to accomplish their task. Google has engineered a very friendly
interface for the API explorer, so it should be fairly obvious when an API
method requires input to execute.


## Info for Udacity Project Reviewer

The following sections contain my written responses to application design
questions that were presented as part of this project, as well as additional
information as it is deemed necessary.


## Task One: Design Choices

*Explain your design choices for session and speaker implementation.*

First of all, I decided that speakers should be represented as their own
entities, rather than by using strings. It would be useful to store
additional data describing the speakers, which would in turn be helpful
to the users and administrators of the application. Also, storing only
the speaker's name as a string, rather than creating an entity, could lead
to name collisions. This would be a big problem for the getSessionsBySpeaker
API, which would return all sessions hosted by speakers with the name
"John Smith", for example, without any clue as to whether or not any sessions
are actually hosted by the same "John Smith".

When modeling the relationship between conferences and sessions, I decided
to avoid using the ancestor relationship in favor of using a foreign key
type of relationship. The session kind defines a KeyProperty field in which
a session entity stores the key for the conference entity to which it belongs.
Similarly, a session entity also stores the key for the speaker entity that
represents the speaker who is hosting the session. Going the ancestor route
may make queries look a little neater, however, I've learned throughout the
"Building Scalable Apps in Python" course that it's often the best decision to
utilize the eventual consistency model of the datastore unless it's absolutely
necessary to guarantee strong consistency. This is due to the fact that greater
scalability and responsiveness can be achieved when the system isn't bound to
the constraints of the strong consistency model. For example, the more entities
that share a common ancestor path, the greater the chances your application
has of exceeding the "one write per second for a single entity group" recommended
limit. Breaking that barrier can result in a greater number of failures, [according
to the documentation](https://cloud.google.com/appengine/articles/scaling/contention).
