import subprocess
import gitlab


class GitLabRepo:
    def __init__(self, name=None, path=None, creator=None, mirror=None):
        self.name = name
        self.mirror = mirror
        self.creator = creator
        self.path = path

    def to_database(self):
        return {
            "_id": self.path,
            "name": self.name,
            "creator": self.creator,
            "mirror": self.mirror
        }


class SKAGitLab(gitlab.Gitlab):
    def __init__(self):
        gitlab.Gitlab.__init__(self, 'https://gitlab.com', private_token='MX_2Q5yUqYvHWexVYaxu')


def list_gitlab_repositories():
    gl = SKAGitLab()

    group = gl.groups.get(3180705)  # Group ID of ska-telescope

    projects = group.projects.list(all=True, order_by="name", sort="asc")

    result = []
    for project in projects:
        creator = gl.users.get(project.creator_id).username
        result.append(GitLabRepo(name=project.name, path=project.path))

    return result


def list_ska_users():
    gl = SKAGitLab()
    return gl.projects.get(9070656).members.all(all=True)  # developer.skatelescope.org project ID


def create_gitlab_repo(parameters):
    group_id = 3180705
    name = parameters['project_name']
    maintainer_ids = parameters['maintainer_ids']

    if 'template' in parameters:
        template = parameters['template']
    else:
        template = None

    gl = SKAGitLab()

    params = {'name': name, 'namespace_id': group_id, 'visibility': "public"}
    if template:
        params['use_custom_template'] = True
        params['group_with_project_templates_id'] = 5901724
        params['template_name'] = template

    project = gl.projects.create(params)

    # Share project with SKA Reporters group:
    project.share(6051772, gitlab.REPORTER_ACCESS)

    # Share project with SKA Developers group:
    project.share(6051706, gitlab.DEVELOPER_ACCESS)

    # Add maintainer users
    if maintainer_ids[0] is not None:
        for user_id in maintainer_ids:
            try:
                member = project.members.create({'user_id': user_id, 'access_level': gitlab.MAINTAINER_ACCESS})
            except Exception as e:
                print(e)
                print("User ID: " + str(user_id))
                print("Project: " + str(project.id))

    if template:
        clone_ska_python_skeleton()

    result = project._attrs

    return result


def clone_ska_python_skeleton():
    pass

