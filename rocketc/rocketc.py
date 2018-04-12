"""
TO-DO: Write a description of what this XBlock is.
"""
import hashlib
import pkg_resources
import requests

from django.conf import settings
from django.contrib.auth.models import User

from xblock.core import XBlock
from xblock.fields import Scope, String
from xblock.fragment import Fragment
from xblockutils.resources import ResourceLoader
from xblockutils.settings import XBlockWithSettingsMixin

LOADER = ResourceLoader(__name__)


@XBlock.wants("user")  # pylint: disable=too-many-ancestors
@XBlock.wants("settings")
class RocketChatXBlock(XBlock, XBlockWithSettingsMixin):
    """
    This class allows to embed a chat window inside a unit course
    and set the necessary variables to config the rocketChat enviroment
    """
    email = String(
        default="", scope=Scope.user_state,
        help="Email in rocketChat",
    )
    rocket_chat_role = String(
        default="user", scope=Scope.user_state,
        help="The defined role in rocketChat"
    )
    default_channel = String(
        default="",
        scope=Scope.content,
        help="This is the initial channel"
        )

    salt = "HarryPotter_and_thePrisoner_of _Azkaban"

    xblock_settings = {}

    def resource_string(self, path):
        """Handy helper for getting resources from our kit."""
        # pylint: disable=no-self-use
        data = pkg_resources.resource_string(__name__, path)
        return data.decode("utf8")

    def student_view(self, context=None):
        """
        The primary view of the RocketChatXBlock, shown to students
        when viewing courses.
        """

        in_studio_runtime = hasattr(
            self.xmodule_runtime, 'is_author_mode')  # pylint: disable=no-member

        if in_studio_runtime:
            return self.author_view(context)

        context["response"] = self.init()
        context["user_data"] = self.user_data
        context["admin_data"] = self.default_channel

        frag = Fragment(LOADER.render_template(
            'static/html/rocketc.html', context))
        frag.add_css(self.resource_string("static/css/rocketc.css"))
        frag.add_javascript(self.resource_string("static/js/src/rocketc.js"))
        frag.initialize_js('RocketChatXBlock')
        return frag

    def author_view(self, context=None):
        """  Returns author view fragment on Studio """
        # pylint: disable=unused-argument
        frag = Fragment(u"Studio Runtime RocketChatXBlock")
        frag.add_css(self.resource_string("static/css/rocketc.css"))
        frag.add_javascript(self.resource_string("static/js/src/rocketc.js"))
        frag.initialize_js('RocketChatXBlock')

        return frag

    def studio_view(self, context=None):
        """  Returns edit studio view fragment """
        # pylint: disable=unused-argument, no-self-use
        frag = Fragment(LOADER.render_template(
            'static/html/studio.html', context))
        frag.add_css(self.resource_string("static/css/rocketc.css"))
        frag.add_javascript(self.resource_string("static/js/src/rocketc.js"))
        frag.initialize_js('RocketChatXBlock')

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

    def init(self):
        """
        This method initializes the user's variables and
        log in to rocketchat account
        """
        self.xblock_settings = self.get_xblock_settings()
        self.url_api_rocket_chat = self.get_url_api_rocket_chat(  # pylint: disable=attribute-defined-outside-init
        )
        self.get_admin_data()
        self.get_user_data()

        self.user_data["url_service"] = self.xblock_settings["url_service"]
        user_data = self.user_data

        response = self.login(user_data)
        if response['success']:
            response = response['data']
            user_id = response['userId']
            self._update_user(user_id, user_data["username"], user_data["email"])
            self.add_to_course_group(user_data["course"], user_id)
            if user_data["role"] == "instructor" and self.rocket_chat_role == "user":
                self.change_role(user_id, "bot")
            return response
        else:
            return response['errorType']

    def get_url_api_rocket_chat(self):
        """
        This method retunrs the rocketChat url service where someone can acces to API
        """
        xblock_settings = self.xblock_settings
        if "url_service" in xblock_settings:
            return "/".join([xblock_settings["url_service"], "api", "v1"])

        return "/".join(["http://localhost:3000", "api", "v1"])

    def get_user_data(self):
        """
        This method initializes the user's parameters
        """
        runtime = self.xmodule_runtime  # pylint: disable=no-member
        user = runtime.service(self, 'user').get_current_user()
        user_data = {}
        user_data["email"] = user.emails[0]
        user_data["role"] = runtime.get_user_role()
        user_data["course"] = runtime.course_id.course
        user_data["username"] = user.opt_attrs['edx-platform.username']
        user_data["anonymous_student_id"] = runtime.anonymous_student_id
        user_data["default_group"] = self.default_channel
        self.user_data = user_data  # pylint: disable=attribute-defined-outside-init

    def get_admin_data(self):
        """
        This method initializes admin's authToken and userId
        """
        try:
            user = self.xblock_settings["admin_user"]
            password = self.xblock_settings["admin_pass"]
        except KeyError:
            raise

        url = "{}/{}".format(self.url_api_rocket_chat, "login")
        data = {"user": user, "password": password}
        headers = {"Content-type": "application/json"}
        response = requests.post(url=url, json=data, headers=headers)
        self.admin_data = {}  # pylint: disable=attribute-defined-outside-init
        self.admin_data["auth_token"] = response.json()["data"]["authToken"]
        self.admin_data["user_id"] = response.json()["data"]["userId"]

    def search_rocket_chat_user(self, username):
        """
        This method allows to get a user from RocketChat data base
        """
        url_path = "{}?{}={}".format("users.info", "username", username)

        return self.request_rocket_chat("get", url_path)

    def login(self, user_data):
        """
        This method allows to get the user's authToken and id
        or creates a user to login in RocketChat
        """
        rocket_chat_user = self.search_rocket_chat_user(user_data["username"])

        if rocket_chat_user['success']:
            data = self.create_token(user_data["username"])

        else:
            self.create_user(user_data["anonymous_student_id"],
                             user_data["email"], user_data["username"])
            data = self.create_token(user_data["username"])

        return data

    def create_token(self, username):
        """
        This method generates a token that allows to login
        """
        url_path = "users.createToken"
        data = {'username': username}
        return self.request_rocket_chat("post", url_path, data)

    def change_role(self, user_id, role):
        """
        This method allows to change the user's role
        """
        data = {"userId": user_id, "data": {"roles": [role]}}
        response = self.request_rocket_chat(
            "post", "users.update", data)
        if response["success"]:
            self.rocket_chat_role = role

    def create_user(self, name, email, username):
        """
        This method creates a user with a specific name, username, email and password.
        The password is a result from a SHA1 function with the name and salt.
        """
        password = "{}{}".format(name, self.salt)
        password = hashlib.sha1(password).hexdigest()
        data = {"name": name, "email": email,
                "password": password, "username": username}
        return self.request_rocket_chat("post", "users.create", data)

    def add_to_course_group(self, group_name, user_id):
        """
        This method add the user to the default course channel
        """
        rocket_chat_group = self.search_rocket_chat_group(group_name)

        if rocket_chat_group['success']:
            self.add_to_group(user_id, rocket_chat_group['group']['_id'])
        else:
            rocket_chat_group = self.create_group(group_name)
            self.add_to_group(user_id, rocket_chat_group['group']['_id'])

        self.group = self.search_rocket_chat_group(  # pylint: disable=attribute-defined-outside-init
            group_name)

    def search_rocket_chat_group(self, room_name):
        """
        This method gets a group with a specific name and returns a json with group's info
        """
        url_path = "{}?{}={}".format("groups.info", "roomName", room_name)
        return self.request_rocket_chat("get", url_path)

    def add_to_group(self, user_id, room_id):
        """
        This method add any user to any group
        """
        url_path = "groups.invite"
        data = {"roomId": room_id, "userId": user_id}
        return self.request_rocket_chat("post", url_path, data)

    def create_group(self, name):
        """
        This method creates a group with a specific name.
        """
        url_path = "groups.create"
        data = {"name": name}
        self.request_rocket_chat("post", url_path, data)

    def request_rocket_chat(self, method, url_path, data=None):
        """
        This method generates a call to the RocketChat API and returns a json with the response
        """
        headers = {"X-Auth-Token": self.admin_data["auth_token"],
                   "X-User-Id": self.admin_data["user_id"], "Content-type": "application/json"}
        url = "{}/{}".format(self.url_api_rocket_chat, url_path)
        if method == "post":
            response = requests.post(url=url, json=data, headers=headers)
        else:
            response = requests.get(url=url, headers=headers)
        return response.json()

    def _user_image_url(self):
        """Returns an image url for the current user"""
        from openedx_dependencies import get_profile_image_urls_for_user  # pylint: disable=relative-import
        current_user = User.objects.get(username=self.user_data["username"])
        base_url = settings.LMS_ROOT_URL
        profile_image_url = get_profile_image_urls_for_user(current_user)[
            "full"]
        image_url = "{}{}".format(base_url, profile_image_url)
        return image_url

    def _set_avatar(self, username):
        image_url = self._user_image_url()
        url_path = "users.setAvatar"
        data = {"username": username, "avatarUrl": image_url}
        self.request_rocket_chat("post", url_path, data)

    def _update_user(self, user_id, username, email):
        """
        This method allows to update The user data
        """
        if email != self.email:
            url_path = "users.update"
            data = {"userId": user_id, "data": {"email": email}}
            response = self.request_rocket_chat("post", url_path, data)
            if response["success"]:
                self.email = email
        self._set_avatar(username)

    @XBlock.json_handler
    def set_default_channel(self, data, suffix=""):
        """
        This method set the default variable for the channels
        """
        default_channel = data["channel"]
        if default_channel != " " and default_channel!= None:
            default_channel = default_channel.replace(" ", "_")
            self.create_group(default_channel)
            self.default_channel = default_channel

    def add_to_default_group(self, group_name, user_id):
        """
        """
        group_info = self.search_rocket_chat_group( group_name)

        if group_info["success"]:
            self.add_to_group(user_id, group_info['group']['_id'])
            return True
        return False
