import json
import logging
import requests
import argparse

AUTH_URL = "https://auth.docker.io/token?service=registry.docker.io&scope=repository"
REG_V2_URL = "https://registry.hub.docker.com/v2/"
TAGS_V2_URI = "/tags/list"
MANIFESTS_V2_URI = "/manifests/"

logging.basicConfig(
    level=logging.INFO,
    handlers=[
        logging.FileHandler("cycode_exercise.log"),
        logging.StreamHandler()
    ]
)


def argument_parser():
    """
    General argument parser function for module
    :return:
    """

    parser = argparse.ArgumentParser(
        description='Docker Hub Repository Tag/Manifest/Cosign Info')
    parser.add_argument('-r', '--repository',
                        type=str,
                        required=True,
                        help='DockerHub registry repository name [String]. '
                             'e.g: "library/ubuntu", "yossireuven/repo-info"')
    parser.add_argument('-l', '--limit',
                        type=int,
                        default=10,
                        help='print limit of objects (tags, manifest) [Int]. [Default=10]')
    return parser.parse_args()


class RepoTagInfo:
    def __init__(self, repo_name, print_limit):
        self.repo_name = repo_name
        self.repo_token = self.get_token()
        self.repo_tags = []
        self._print_limit = print_limit

    def get_token(self):
        # function constants
        _auth_url = f'{AUTH_URL}:{self.repo_name}:pull'
        # get token for given repository
        r_auth_json = self.get_json_from_url(_auth_url)
        if r_auth_json and 'token' in r_auth_json:
            logging.info(f'Token acquired successfully from \"{self.repo_name}\"')
            return r_auth_json['token']
        logging.error(f'Could not acquire token from \"{self.repo_name}\". Quitting...')
        exit(1)

    def get_and_print_tags(self):
        # function constants
        headers = {"Authorization": f"Bearer {self.repo_token}"}
        _tags_url = f'{REG_V2_URL}{self.repo_name}{TAGS_V2_URI}'
        # fetch repository tags, store to instance variable and print (by limit) them
        r_tags_url_json = self.get_json_from_url(_tags_url, headers=headers)
        if r_tags_url_json and 'tags' in r_tags_url_json:
            self.repo_tags = r_tags_url_json['tags']
            logging.info(f'Found total of: {len(self.repo_tags)} Tags in \"{self.repo_name}\"')
            logging.info(
                f'First {self._print_limit} Tags in \"{self.repo_name}\": {self.repo_tags[:self._print_limit]}')
        else:
            logging.error(f'Error occurred when trying to get tags from \"{self.repo_name}\". Quitting...')
            exit(1)

    def get_and_print_manifests(self):
        headers = {
            "Authorization": f"Bearer {self.repo_token}",
            "Accept": "application/vnd.docker.distribution.manifest.v2+json"
        }
        for tag in self.repo_tags:
            if str(tag).startswith('sha256-') and str(tag).endswith('.sig'):
                # signature tage for an image in the repository, no need to pull manifest
                continue
            _manifest_url = f'{REG_V2_URL}{self.repo_name}{MANIFESTS_V2_URI}{tag}'
            r_tag_manifest = self.get_json_from_url(_manifest_url, headers=headers, with_res_headers=True)
            if r_tag_manifest:
                self.is_signed_artifact(tag, r_tag_manifest)
            logging.info(f'Manifest for \"{self.repo_name}:{tag}\":\n{r_tag_manifest}')

    def is_signed_artifact(self, tag, r_tag_manifest):
        if 'docker-content-digest' in r_tag_manifest['headers']:
            image_digest = r_tag_manifest['headers']['docker-content-digest'].strip('sha256:')
            image_digest = f'sha256-{image_digest}.sig'  # format as cosign signatures file format
            if image_digest in self.repo_tags:
                logging.info(f'Signed! - \"{self.repo_name}:{tag}\" have Cosign signature.')
            del r_tag_manifest['headers']

    @staticmethod
    def get_json_from_url(url, headers=None, with_res_headers=False):
        try:
            response = requests.get(url, headers=headers)
            if response.status_code == requests.codes.OK:
                try:
                    json_data = json.loads(response.text)
                    if with_res_headers:
                        json_data['headers'] = response.headers
                    return json_data
                except json.JSONDecodeError as err_msg:
                    logging.error(f'Could not decode response from {url}.\n{err_msg}')
            elif response.status_code == requests.codes.NOT_FOUND:
                logging.error(f'Page not found: {url}. Quitting...')
            elif response.status_code == requests.codes.UNAUTHORIZED:
                logging.error(f'Unauthorized access: {url}. Quitting...')
            else:
                logging.error(f'Unknown error occurred when trying to access: {url}.\nError-Code: {response.reason}')
        except requests.exceptions.RequestException as err_msg:
            logging.error(f'Unknown error occurred when trying to access: {url}.\n{err_msg}')
        return {}


if __name__ == '__main__':
    args = argument_parser()
    logging.info(f'Repository Info Fetcher - \"{args.repository}\"')
    repo_info = RepoTagInfo(args.repository, args.limit)
    repo_info.get_and_print_tags()
    repo_info.get_and_print_manifests()
