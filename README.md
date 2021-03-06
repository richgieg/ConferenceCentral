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
to name collisions. This would be a big problem for the `getSessionsBySpeaker`
API, which would return all sessions hosted by speakers with the name
"John Smith", for example, without any clue as to whether or not any sessions
are actually hosted by the same "John Smith".

When modeling the relationship between conferences and sessions, I decided
to avoid using the ancestor relationship in favor of using a foreign key
type of relationship. The session kind defines a `KeyProperty` field in which
a session entity stores the key for the conference entity to which it belongs.
Similarly, a session entity also stores the key for the speaker entity that
represents the speaker who is hosting the session. Although going the ancestor route
may make queries look a little neater, I've learned throughout the
"Building Scalable Apps in Python" course that it's often the best decision to
utilize the eventual consistency model of the datastore unless it's absolutely
necessary to guarantee strong consistency. This is due to the fact that greater
scalability and responsiveness can be achieved when the system isn't bound to
the constraints of the strong consistency model. For example, the more entities
that share a common ancestor path, the greater the chances your application
has of exceeding the "one write per second for a single entity group" recommended
limit. Breaking that barrier can result in a greater number of failures, [according
to the documentation](https://cloud.google.com/appengine/articles/scaling/contention).


## Task One: Implementation

I implemented the following Endpoints API methods to support the requirements of
this task:

**Required:**
- `createSession`
- `getConferenceSessions`
- `getConferenceSessionsByType`
- `getSessionsBySpeaker`

**Additional:**
- `createSpeaker`
- `getSpeakers`


## Task Two: Session Wishlists

*Users should be able to mark some sessions that they are interested in and
retrieve their own current wishlist.*

I implemented the following Endpoints API methods to support the requirements of
this task:

**Required:**
- `addSessionToWishlist`
- `getSessionsInWishlist`

**Additional:**
- `removeSessionFromWishlist`


## Task Three: Create Indexes

*Make sure the indexes support the type of queries required by the new
Endpoints methods.*

I added indexes to `index.yaml` to support all additional queries. Also, I wrote
extensive documentation in `index.yaml` explaining the algorithm I used to generate
the smallest number of indexes needed to handle all possible filter combinations that
users may submit to the `queryConferences` API. I believe this documentation does a great
job in demonstrating my understanding of how datastore indexes work. Also, I believe
it demonstrates my grasp of basic discrete mathematics and computer science concepts
(counting, combinations).


## Task Three: New Queries

*Think about other types of queries that would be useful for this application. Describe
the purpose of two new queries and implement them.*

I believe that users should be able to attain a list of conferences in which each
conference matches one or more topics from a list of topics that the user supplies.
The existing query implementation is AND-based, so combining multiple equality filters
that target the topics field only serves to further constrain and diminish the results.
My proposed query type makes it possible for a user to enter a list of topics in which
they're interested and be presented with a list of conferences that match one or more
of the topics in their list.

Also, I believe that users should similarly be able to attain a list of sessions in
which each session matches one or more highlights from a list of highlights that the
user supplies. This will allow the user to enter a list of highlights in which
they're interested and be presented with a list of sessions that match one or more
of the highlights in their list.

I implemented the following Endpoints API methods to support the requirements of
this task:

- `getConferencesByTopicSearch`
- `getSessionsByHighlightSearch`


## Task Three: Query Problem

*Imagine a user doesn't like workshop sessions, nor sessions that start after 7:00pm.
How would you handle a query for all non-workshop sessions before 7:00pm? What is
the problem for implementing this query? How would you solve it?*

The issue with this query is that it proposes utilizing inequality filters on two
different properties. A limitation of the Google App Engine datastore is that it can
only support applying inequality filters to at most one property in a query. Since I
implemented a `SessionType` enum which governs the accepted values for the `typeOfSession`
property on session entities, this this problem can be solved by converting the single
session-type `!=` filter into a list of session-type `==` filters for all session types
from the `SessionType` enum except for the session type that the user wants to exclude.
The list can then be passed into `ndb.OR` to "or" them together. This results in all
sessions that are of any session-type, except for the excluded session-type, to be
matched, provided they meet the requirements of the `startTime` inequality filter.

I implemented the following Endpoints API method to demonstrate the above solution:

- `getSessionsDoubleInequalityDemo`


## Task Four: Add a Task to the Task Queue

*When a new session is added to a conference, check the speaker. If there is more than
one session by this speaker at this conference, add a new Memcache entry that features
the speaker and session names. This should be handled using App Engine's Task Queue.*

I implemented the following Endpoints API method to support the requirements of
this task:

- `getFeaturedSpeaker`


## Potential Extra Credit

While working on this project I noticed a bug when unregistering from a conference
through the front-end. The number which represents the quantity of people registered
for the conference became a seemingly-random negative number. I ended up digging in
to the issue and it turns out the negative number wasn't random at all, but it was
caused by the back-end code returning a numeric value as a string in the JSON used
to render the page. Havoc then ensued once JavaScript performed calculations with
actual integers and strings containing integer representations. An in-depth analysis
can be found in the description for the [issue I opened](https://github.com/udacity/ud858/issues/7)
on GitHub. The repaired code I committed can be found [here](https://github.com/udacity/ud858/commit/82822d647278c6516997b8d65c0c93657aef4775).
The pull request I submitted, which was merged by a Udacity engineer, can be found
[here](https://github.com/udacity/ud858/pull/8).
