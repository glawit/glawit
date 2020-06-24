import base64
import json
import logging

import gql
import gql.transport.requests
import jinja2

import glawit.core.access
import glawit.core.jinja2

logger = logging.getLogger(
)


def process_request(config, handler, request):
    github_owner = config['GitHub']['owner']
    github_repo = config['GitHub']['repo']
    store_bucket = config['large_file_store']['bucket_name']

    body = request['body']
    headers = request['headers']

    try:
        authorization_header_value = headers['authorization']
    except KeyError:
        logger.error(
            'missing Authorization header',
        )

        response = {
            'statusCode': 401,
            'headers': {
                'Content-Type': 'application/vnd.git-lfs+json',
                'LFS-Authenticate': 'Basic realm="Git LFS", charset="UTF-8"',
            },
            'body': {
                'message': 'Pass your GitHub user as username and a personal token as password',
                'documentation_url': 'https://help.github.com/en/github/authenticating-to-github/creating-a-personal-access-token-for-the-command-line',
            },
            'isBase64Encoded': False,
        }
    else:
        logger.debug(
            'Authorization header present',
        )

#        pieces = authorization_header_value.split(
#            maxsplit=1,
#            sep=' ',
#        )
#
#        authorization_type = pieces[0]
#        authorization_credentials = pieces[1]
#
#        logger.debug(
#            'authorization type: %s',
#            authorization_type,
#        )
#
#        token = None
#
#        if authorization_type == 'Basic':
#            logger.debug(
#                'encoded authorization credentials: %s',
#                authorization_credentials,
#            )
#
#            authorization_credentials = base64.b64decode(
#                authorization_credentials,
#                validate=True,
#            )
#
#            authorization_credentials = authorization_credentials.decode(
#                'utf-8',
#            )
#
#            logger.debug(
#                'decoded authorization credentials: %s',
#                authorization_credentials,
#            )
#
#            pieces = authorization_credentials.split(
#                sep=':',
#            )
#
#            username = pieces[0]
#            password = pieces[1]
#
#            logger.debug(
#                'username: %s',
#                username,
#            )
#
#            logger.debug(
#                'password: %s',
#                password,
#            )
#
#            token = password
#        elif authorization_type == 'Token':
#            token = authorization_credentials
#        else:
#            response = {
#                'statusCode': 401,
#                'headers': {
#                    'Content-Type': 'application/vnd.git-lfs+json',
#                    'LFS-Authenticate': 'Basic realm="Git LFS", charset="UTF-8"',
#                },
#                'body': {
#                    'message': 'missing authentication',
#                    # FIXME
#                    'documentation_url': 'https://mo.in/',
#                },
#                'isBase64Encoded': False,
#            }

        transport = gql.transport.requests.RequestsHTTPTransport(
            headers={
                'Authorization': authorization_header_value,
            },
            url='https://api.github.com/graphql',
        )

        client = gql.Client(
            fetch_schema_from_transport=False,
            transport=transport,
        )

        jinja2_environment = jinja2.Environment(
            loader=glawit.core.jinja2.loader,
        )

        template = jinja2_environment.get_template(
            'github.graphql.j2',
        )

        graphql_query_code = template.render(
            owner=github_owner,
            repo=github_repo,
        )

        graphql_query = gql.gql(
            graphql_query_code,
        )

        try:
            result = client.execute(
                graphql_query,
            )
        except Exception:
            response = {
                'statusCode': 403,
                'headers': {
                    'Content-Type': 'application/vnd.git-lfs+json',
                },
                'body': {
                    'message': 'The GitHub API token provided lacks access to this GitHub repository.',
                    # FIXME
                    'documentation_url': 'https://mo.in/',
                },
                'isBase64Encoded': False,
            }
        else:
            logger.debug(
                'GitHub query result: %s',
                result,
            )

            result_repository = result['repository']
            if result_repository:
                viewer_permission = result_repository['viewerPermission']

                viewer_access = glawit.core.access.RepositoryAccess[viewer_permission]

                # FIXME
                minimum_access_setting = 'ADMIN'
                minimum_access = glawit.core.access.RepositoryAccess[minimum_access_setting]

                enough = viewer_access >= minimum_access

                if enough:
                    body_type = type(
                        body,
                    )

                    if body_type == dict:
                        data = body
                    else:
                        # FIXME
                        #assert header_says_body_is_json

                        logger.debug(
                            'body: %s',
                            body,
                        )

                        data = json.loads(
                            body,
                        )

                    response = handler(
                        config=config,
                        data=data,
                        viewer_access=viewer_access,
                    )
                else:
                    response = {
                        'statusCode': 403,
                        'headers': {
                            'Content-Type': 'application/vnd.git-lfs+json',
                        },
                        'body': {
                            'message': 'Your permission level for this repository is not enough.',
                            'documentation_url': 'https://help.github.com/en/github/getting-started-with-github/access-permissions-on-github',
                        },
                        'isBase64Encoded': False,
                    }
            else:
                response = {
                    'statusCode': 403,
                    'headers': {
                        'Content-Type': 'application/vnd.git-lfs+json',
                    },
                    'body': {
                        'message': 'It seems the GitHub repository is private and the GitHub API token provided lacks access to private repositories. Grant it the corresponding scope and try again.',
                        'documentation_url': 'https://developer.github.com/apps/building-oauth-apps/understanding-scopes-for-oauth-apps/#available-scopes',
                    },
                    'isBase64Encoded': False,
                }

    try:
        body = response['body']
    except KeyError:
        pass
    else:
        body_json = json.dumps(
            body,
        )

        response['body'] = body_json

    return response
