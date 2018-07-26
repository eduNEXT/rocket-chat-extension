"""
TO-DO: Write a description of what this XBlock is.
"""
import logging
import json
import re
import pkg_resources

from api_teams import ApiTeams  # pylint: disable=relative-import
from api_rocket_chat import ApiRocketChat  # pylint: disable=relative-import

from django.conf import settings
from django.contrib.auth.models import User

from xblock.core import XBlock
from xblock.fields import Scope, String, Boolean, DateTime, Integer, Float
from xblock.fragment import Fragment
from xblockutils.resources import ResourceLoader
from xblockutils.settings import XBlockWithSettingsMixin
from xblockutils.studio_editable import StudioEditableXBlockMixin


LOADER = ResourceLoader(__name__)
LOG = logging.getLogger(__name__)


@XBlock.wants("user")  # pylint: disable=too-many-ancestors
@XBlock.wants("settings")
class RocketChatXBlock(XBlock, XBlockWithSettingsMixin, StudioEditableXBlockMixin):
    """
    This class allows to embed a chat window inside a unit course
    and set the necessary variables to config the rocketChat enviroment
    """
    display_name = String(
        display_name="Display Name",
        scope=Scope.settings,
        default="Rocket Chat"
    )
    email = String(
        default="", scope=Scope.user_state,
        help="Email in rocketChat",
    )
    rocket_chat_role = String(
        default="user", scope=Scope.user_state,
        help="The defined role in rocketChat"
    )

    default_channel = String(
        display_name="Specific Channel",
        scope=Scope.content,
        help="This field allows to select the channel that would be accesible in the unit",
        values_provider=lambda self: self.get_groups(),
    )

    ui_is_block = Boolean(
        default=False,
        scope=Scope.user_state,
        help="This is the flag for the initial channel",
    )

    selected_view = String(
        display_name="Select Channel",
        default="Main View",
        scope=Scope.content,
        help="This field allows to select the channel that would be accesible in the unit",
        values_provider=lambda self: self.channels_enabled(),
    )

    team_channel = String(
        default="",
        scope=Scope.user_state
    )

    emoji = String(
        display_name="Emoji to grade with",
        default="",
        scope=Scope.settings,
        help="Select the emoji which you want to grade",
    )

    oldest = DateTime(
        display_name="Date From",
        default=None,
        scope=Scope.settings,
        help="ISO-8601 formatted string representing the start date of this assignment."
    )

    latest = DateTime(
        display_name="Date To",
        default=None,
        scope=Scope.settings,
        help="ISO-8601 formatted string representing the due date of this assignment."
    )

    target_reaction = Integer(
        display_name="Target Reaction Count",
        default=5,
        scope=Scope.settings,
        help="Target value in order to achieve a defined grade."
    )

    graded_activity = Boolean(
        display_name="Graded Activity",
        default=False,
        scope=Scope.settings,
    )

    weight = Float(
        display_name="Score",
        help="Defines the number of points each problem is worth. ",
        values={"min": 0, "step": .1},
        default=1,
        scope=Scope.settings
    )

    grade = Float(
        scope=Scope.user_state,
        default=0
    )

    count_messages = Integer(
        display_name="Last Messages",
        default=1000,
        scope=Scope.settings,
        help="The amount of messages to retrieve"
    )

    has_score = True
    team_view = True

    VIEWS = ["Main View", "Team Discussion", "Specific Channel"]

    # Possible editable fields
    editable_fields = ('selected_view', 'default_channel',
                       'graded_activity', 'emoji', 'target_reaction', 'oldest', 'latest', 'weight', 'count_messages')

    def resource_string(self, path):
        """Handy helper for getting resources from our kit."""
        # pylint: disable=no-self-use
        data = pkg_resources.resource_string(__name__, path)
        return data.decode("utf8")

    @XBlock.supports('multi_device') # Mark as mobile-friendly
    def student_view(self, context=None):
        """
        The primary view of the RocketChatXBlock, shown to students
        when viewing courses.
        """

        in_studio_runtime = hasattr(
            self.xmodule_runtime, 'is_author_mode')  # pylint: disable=no-member

        if in_studio_runtime:
            return self.author_view(context)

        context = {
            "response": self.init(),
            "user_data": self.user_data,
            "ui_is_block": self.ui_is_block,
            "team_view": self.team_view,
            "public_url_service": self.server_data["public_url_service"]
        }

        frag = Fragment(LOADER.render_template(
            'static/html/rocketc.html', context))
        frag.add_css(self.resource_string("static/css/rocketc.css"))
        frag.add_javascript(self.resource_string("static/js/src/rocketc.js"))
        frag.initialize_js('RocketChatXBlock')
        return frag

    def author_view(self, context=None):
        """  Returns author view fragment on Studio """
        # pylint: disable=unused-argument
        self.api_rocket_chat.convert_to_private_channel("general")
        frag = Fragment(u"Studio Runtime RocketChatXBlock")
        frag.initialize_js('RocketChatXBlock')

        return frag

    def studio_view(self, context=None):
        """  Returns edit studio view fragment """
        frag = super(RocketChatXBlock, self).studio_view(context)
        frag.add_content(LOADER.render_template(
            'static/html/studio.html', context))
        frag.add_css(self.resource_string("static/css/rocketc.css"))
        frag.add_javascript(self.resource_string("static/js/src/studio_view.js"))
        frag.initialize_js('StudioViewEdit')
        return frag

    # TO-DO: change this to create the scenarios you'd like to see in the
    # workbench while developing your XBlock.
    @staticmethod
    def workbench_scenarios():
        """A canned scenario for display in the workbench."""
        return [
            ("RocketChatXBlock",
             """<rocketc/>
             """),
            ("Multiple RocketChatXBlock",
             """<vertical_demo>
                <rocketc/>
                <rocketc/>
                <rocketc/>
                </vertical_demo>
             """),
        ]

    @property
    def api_rocket_chat(self):
        """
        Creates an ApiRcoketChat object
        """
        try:
            user = self.xblock_settings["admin_user"]
            password = self.xblock_settings["admin_pass"]
        except KeyError:
            LOG.exception("The admin's settings has not been found")
            raise
        api = ApiRocketChat(user, password, self.server_data["private_url_service"])

        LOG.info("Api rocketChat initialize: %s ", api)

        return api

    @property
    def api_teams(self):
        """
        Creates an ApiTeams object
        """
        try:
            user = self.xblock_settings["username"]
            password = self.xblock_settings["password"]
            client_id = self.xblock_settings["client_id"]
            client_secret = self.xblock_settings["client_secret"]
        except KeyError:
            raise

        server_url = settings.LMS_ROOT_URL

        api = ApiTeams(user, password, client_id, client_secret, server_url)

        LOG.info("Api Teams initialize: %s ", api)

        return api

    @property
    def server_data(self):
        """
        This method allows to get private and public url from xblock settings
        """
        xblock_settings = self.xblock_settings
        server_data = {}
        server_data["private_url_service"] = xblock_settings["private_url_service"]
        server_data["public_url_service"] = xblock_settings["public_url_service"]
        return server_data

    @property
    def user_data(self):
        """
        This method initializes the user's parameters
        """
        runtime = self.xmodule_runtime  # pylint: disable=no-member
        user = runtime.service(self, 'user').get_current_user()
        user_data = {}
        user_data["email"] = user.emails[0]
        user_data["role"] = runtime.get_user_role()
        user_data["course_id"] = runtime.course_id
        user_data["course"] = re.sub('[^A-Za-z0-9]+', '', runtime.course_id._to_string()) # pylint: disable=protected-access
        user_data["username"] = user.opt_attrs['edx-platform.username']
        user_data["anonymous_student_id"] = runtime.anonymous_student_id

        if self.selected_view == self.VIEWS[1]:
            user_data["default_group"] = self.team_channel
        else:
            user_data["default_group"] = self.default_channel

        return user_data

    @property
    def xblock_settings(self):
        """
        This method allows to get the xblock settings
        """
        return self.get_xblock_settings()

    def channels_enabled(self):
        """
        This method returns a list with the channel options
        """
        if self._teams_is_enabled():
            return self.VIEWS
        view = list(self.VIEWS)
        view.remove(self.VIEWS[1])
        return view

    def get_groups(self):
        """
        This method lists the existing groups
        """
        groups = self.api_rocket_chat.get_groups()
        groups = [group for group in groups if not group.startswith("Team")]
        return groups

    def init(self):
        """
        This method initializes the user's variables and
        log in to rocketchat account
        """

        user_data = self.user_data

        response = self.login(user_data)
        if response['success']:
            response = response['data']
            user_id = response['userId']

            self._join_user_to_groups(user_id, user_data)
            self._update_user(user_id, user_data)

            if user_data["role"] == "instructor" and self.rocket_chat_role != "bot":
                self.api_rocket_chat.change_user_role(user_id, "bot")

            self._grading_discussions()
            return response
        else:
            return response['errorType']

    def login(self, user_data):
        """
        This method allows to get the user's authToken and id
        or creates a user to login in RocketChat
        """
        api = self.api_rocket_chat

        rocket_chat_user = api.search_rocket_chat_user(user_data["username"])
        LOG.info("Login method: result search user: %s", rocket_chat_user["success"])

        if rocket_chat_user['success']:
            data = api.create_token(user_data["username"])

        else:
            response = api.create_user(user_data["anonymous_student_id"], user_data[
                "email"], user_data["username"])
            LOG.info("Login method: result create user : %s", response)

            data = api.create_token(user_data["username"])

        LOG.info("Login method: result create token: %s", data)

        return data

    def _add_user_to_course_group(self, group_name, user_id):
        """
        This method add the user to the default course channel
        """
        api = self.api_rocket_chat
        rocket_chat_group = api.search_rocket_chat_group(group_name)

        if rocket_chat_group['success']:
            api.add_user_to_group(user_id, rocket_chat_group['group']['_id'])
        else:
            rocket_chat_group = api.create_group(group_name, [self.user_data["username"]])

        self.group = api.search_rocket_chat_group(  # pylint: disable=attribute-defined-outside-init
            group_name)

    def _add_user_to_default_group(self, group_name, user_id):
        """
        """
        api = self.api_rocket_chat
        group_info = api.search_rocket_chat_group(group_name)

        if group_info["success"]:
            api.add_user_to_group(user_id, group_info['group']['_id'])
            return True
        return False

    def _add_user_to_team_group(self, user_id, username, course_id):
        """
        Add the user to team's group in rocketChat
        """
        team = self._get_team(username, course_id)
        api = self.api_rocket_chat

        if team is None:
            self._remove_user_from_group(self.team_channel, user_id)
            return False
        topic_id = re.sub(r'\W+', '', team["topic_id"])
        team_name = re.sub(r'\W+', '', team["name"])
        group_name = "-".join(["Team", topic_id, team_name])

        if self.team_channel != group_name:
            self._remove_user_from_group(self.team_channel, user_id)

        group_info = api.search_rocket_chat_group(group_name)
        self.team_channel = group_name

        if group_info["success"]:
            response = api.add_user_to_group(user_id, group_info['group']['_id'])
            LOG.info("Add to team group response: %s", response)
            return response["success"]

        response = api.create_group(group_name, [username])
        LOG.info("Add to team group response: %s", response)
        return response["success"]

    def _get_team(self, username, course_id):
        """
        This method gets the user's team
        """
        api = self.api_teams
        team = api.get_user_team(course_id, username)
        LOG.info("Get Team response: %s", team)
        if team:
            return team[0]
        return None

    def _join_user_to_groups(self, user_id, user_data):
        """
        This methodd add the user to the diferent channels
        """
        default_channel = self.default_channel

        if self.selected_view == self.VIEWS[1] and self._teams_is_enabled():
            self.team_view = self._add_user_to_team_group(
                user_id, user_data["username"], user_data["course_id"])
            self.ui_is_block = self.team_view

        elif self.selected_view == self.VIEWS[2]:
            self.ui_is_block = self._add_user_to_default_group(default_channel, user_id)

        else:
            self.ui_is_block = False
            self._add_user_to_course_group(user_data["course"], user_id)

    def _teams_is_enabled(self):
        """
        This method verifies if teams are available
        """
        from openedx_dependencies import modulestore  # pylint: disable=relative-import
        try:
            course_id = self.runtime.course_id  # pylint: disable=no-member
        except AttributeError:
            return False

        course = modulestore().get_course(course_id, depth=0)
        teams_configuration = course.teams_configuration
        LOG.info("Team is enabled result: %s", teams_configuration)
        if "topics" in teams_configuration and teams_configuration["topics"]:
            return True

        return False

    def _update_user(self, user_id, user_data):
        """
        This method updates the email and photo's profile
        """
        api = self.api_rocket_chat
        if user_data["email"] != self.email:
            self.email = api.update_user(user_id, user_data["email"])

        api.set_avatar(user_data["username"], self._user_image_url())

    def _user_image_url(self):
        """Returns an image url for the current user"""
        from openedx_dependencies import get_profile_image_urls_for_user  # pylint: disable=relative-import
        current_user = User.objects.get(username=self.user_data["username"])
        profile_image_url = get_profile_image_urls_for_user(current_user)[
            "full"]

        if profile_image_url.startswith("http"):
            return profile_image_url

        base_url = settings.LMS_ROOT_URL
        image_url = "{}{}".format(base_url, profile_image_url)
        LOG.info("User image url: %s ", image_url)
        return image_url

    @XBlock.json_handler
    def create_group(self, data, suffix=""):
        """
        This method allows to create a group
        """
        # pylint: disable=unused-argument

        api = self.api_rocket_chat

        group_name = data["groupName"]
        description = data["description"]
        topic = data["topic"]

        if group_name == "" or group_name is None:
            return {"success": False, "error": "Group Name is not valid"}

        in_studio_runtime = hasattr(
            self.xmodule_runtime, 'is_author_mode')  # pylint: disable=no-member

        group_name = re.sub(r'\W+', '', group_name)

        if not in_studio_runtime:
            course_id = self.xmodule_runtime.course_id # pylint: disable=no-member
            team = self._get_team(self.user_data["username"], course_id)
            topic = re.sub(r'\W+', '', team["topic_id"])
            team_name = re.sub(r'\W+', '', team["name"])
            group_name = "-".join([topic, team_name, group_name])
            members = self.get_team_members(team)
            members = list(members)
            group = api.create_group(group_name, members)
        else:
            group = api.create_group(group_name)
            if group["success"]:
                self.default_channel = group_name

        if "group" in group:
            group_id = group["group"]["_id"]

            api.set_group_description(group_id, description)
            api.set_group_topic(group_id, topic)

        LOG.info("Method Public Create Group: %s", group)
        return group

    def _remove_user_from_group(self, group_name, user_id):
        """
        This method removes a user form a team
        """
        api = self.api_rocket_chat
        group = api.search_rocket_chat_group(group_name)
        if group["success"]:
            group = group["group"]
            return api.kick_user_from_group(user_id, group["_id"])
        return group

    def get_team_members(self, team):
        """
        This method allows to get the members of a team
        """
        api = self.api_teams
        if team:
            team_id = team["id"]
            members = api.get_members(team_id)
            if members:
                for member in members:
                    yield member["user"]["username"]

    @XBlock.json_handler
    def leave_group(self, data, suffix=""):
        """
        This method allows to leave a group
        """
        # pylint: disable=unused-argument

        api = self.api_rocket_chat
        username = self.user_data["username"]
        user = api.search_rocket_chat_user(username)
        group_name = data["groupName"]

        if not user["success"]:
            return {"success": False, "error": "User is not valid"}

        if group_name == "" or group_name is None:
            return {"success": False, "error": "Group Name is not valid"}

        if group_name == self.team_channel or group_name == self.user_data["course"]:
            return {"success": False, "error": "You Can Not Leave a Main Group"}

        return self._remove_user_from_group(group_name, user["user"]["_id"])

    @XBlock.json_handler
    def get_list_of_groups(self, data, suffix=""):
        """Returns a list with the group names"""
        # pylint: disable=unused-argument
        user_id = data.get("userId", None)
        auth_token = data.get("authToken", None)

        if not user_id or not auth_token:
            LOG.warn("Invalid data for method get_list_of_groups: %s", data)
            return None

        course_id = self.xmodule_runtime.course_id # pylint: disable=no-member
        team = self._get_team(self.user_data["username"], course_id)
        topic = re.sub(r'\W+', '', team["topic_id"])
        team_name = re.sub(r'\W+', '', team["name"])

        regex = "-".join([topic, team_name])
        query = {"name": {"$regex": regex}}
        query = json.dumps(query)

        groups = list(self._get_list_groups(user_id, auth_token, query))
        return groups

    def _get_list_groups(self, user_id, auth_token, query=""):
        """
        This method allows to get a list of group names
        """
        api = self.api_rocket_chat
        groups = api.list_all_groups(user_id, auth_token, query)
        if groups["success"]:
            groups = groups["groups"]
            for group in groups:
                yield group["name"]

    def _get_user_messages(self, group_name, latest="", oldest="", count=100):
        """
        Gets the messages from a user's private group.
        """
        api = self.api_rocket_chat
        rocket_chat_group = api.search_rocket_chat_group(group_name)

        if not rocket_chat_group['success']:
            return None

        group_id = rocket_chat_group['group']['_id']
        messages = api.get_groups_history(room_id=group_id, latest=latest,
                                          oldest=oldest, count=count)

        if not messages["success"]:
            return None

        LOG.info("Messages get user messages: %s ", messages)
        LOG.info("username get user messages: %s ", self.user_data["username"])
        return [message for message in messages["messages"]
                if message["u"]["username"] == self.user_data["username"]]

    def _filter_by_reaction_and_user_role(self, messages, reaction):
        """
        Returns generator with filtered messages by a given reaction
        """
        for message in messages:
            if not reaction in message.get("reactions", {}):
                continue
            usernames = message["reactions"][reaction]["usernames"]

            for username in usernames:
                if self._validate_user_role(username):
                    yield message
                    break

    def _validate_user_role(self, username):
        """
        Returns True if the user is privileged in teams discussions for
        this course.
        """
        from openedx_dependencies import has_discussion_privileges, CourseStaffRole  # pylint: disable=relative-import

        user = User.objects.get(username=username)
        LOG.info("uSERNAME %s ", username)
        if user.is_staff:
            LOG.info("uSERNAME  True ")
            return True
        if CourseStaffRole(self.user_data["course_id"]).has_user(user):
            LOG.info("uSERNAME  True ")
            return True
        LOG.info("uSERNAME  False ")
        return False

    def _grading_discussions(self):
        """
        This method allows to grade contributions to Rocket.Chat given a reaction.
        """
        if not self.graded_activity or self.grade == self.weight:
            return
        messages = self._get_user_messages(self.user_data["default_group"],
                                           self.latest, self.oldest, self.count_messages)
        LOG.info("Messages: %s ", messages)
        messages = list(self._filter_by_reaction_and_user_role(messages, self.emoji))
        LOG.info("Filter Messages: %s ", messages)
        LOG.info("Graded activity %s ", self.graded_activity)
        LOG.info("Graded  %s ", self.grade)
        if len(messages) >= self.target_reaction:
            self.grade = self.weight
            self.runtime.publish(self, 'grade', {'value': self.grade, 'max_value': self.weight})
            LOG.info("publish")

    def max_score(self):
        return self.weight
