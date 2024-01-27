import json
import logging
import re
import urllib.parse
import urllib.request
from pathlib import Path


# Initialize logging
def initialize_logging(level=logging.WARN):
    logging.basicConfig(format="%(levelname)s:  %(message)s", level=logging.NOTSET)
    logger = logging.getLogger()
    logger.setLevel(level)


def _preprocess_output(*args, **kwargs):
    # Turn all paths into relative paths
    CWD = Path.cwd().as_posix()
    if "relative_paths" not in kwargs or kwargs["relative_paths"]:
        args = [re.sub(CWD + "/", "", a) for a in args]

    kwargs.pop("relative_paths", None)
    return args, kwargs


def dbg(*args, **kwargs):
    args, kwargs = _preprocess_output(*args, **kwargs)
    logging.getLogger().debug(*args, **kwargs)


def vrb(*args, **kwargs):
    args, kwargs = _preprocess_output(*args, **kwargs)
    logging.getLogger().info(*args, **kwargs)


def wrn(*args, **kwargs):
    args, kwargs = _preprocess_output(*args, **kwargs)
    logging.getLogger().warning(*args, **kwargs)


class CaddyServerController:
    def __init__(self, site_configs):
        self.site_configs = site_configs

    def update_site_config(self, site_id):
        caddy_config = self.create_config(site_id)
        site_config = self.site_configs.sites[site_id].config
        admin_base_url = site_config["intents"]["serve"]["caddy_server_admin_base_url"]
        self.apply_config(admin_base_url, caddy_config)

    def create_config(self, site_id):
        site_config = self.site_configs.sites[site_id].config
        site_env_hostname = site_config["intents"]["serve"]["hostname"]
        CADDY_MATCH_STATIC_FILES = [
            "*.css",
            "*.js",
            "*.gif",
            "*.png",
            "*.jpg",
            "*.jpeg",
            "*.webp",
            "*.svg",
            "*.woff",
            "*.woff2",
        ]

        CADDY_ROUTES_SECURE = [
            {
                "handle": [
                    {
                        "handler": "subroute",
                        "routes": [
                            {
                                "handle": [
                                    {
                                        "handler": "headers",
                                        "response": {
                                            "set": {
                                                "Cache-Control": [
                                                    "public, max-age=31536000, immutable"
                                                ]
                                            }
                                        },
                                    }
                                ],
                                "match": [{"path": CADDY_MATCH_STATIC_FILES}],
                            },
                            {
                                "handle": [
                                    {
                                        "handler": "headers",
                                        "response": {
                                            "set": {
                                                "Cache-Control": [
                                                    "public, max-age=0, must-revalidate"
                                                ]
                                            }
                                        },
                                    }
                                ],
                                "match": [
                                    {"not": [{"path": CADDY_MATCH_STATIC_FILES}]}
                                ],
                            },
                            {
                                "handle": [
                                    {
                                        "encodings": {"gzip": {}},
                                        "handler": "encode",
                                        "prefer": ["gzip"],
                                    },
                                    {
                                        "handler": "file_server",
                                        "hide": ["/etc/caddy/Caddyfile"],
                                    },
                                ]
                            },
                        ],
                    }
                ],
                "match": [{"host": [site_env_hostname]}],
                "terminal": True,
            }
        ]

        CADDY_ROUTES = [
            {
                "handle": [
                    {
                        "handler": "headers",
                        "response": {
                            "set": {
                                "Cache-Control": ["public, max-age=31536000, immutable"]
                            }
                        },
                    }
                ],
                "match": [{"path": CADDY_MATCH_STATIC_FILES}],
            },
            {
                "handle": [
                    {
                        "handler": "headers",
                        "response": {
                            "set": {
                                "Cache-Control": ["public, max-age=0, must-revalidate"]
                            }
                        },
                    }
                ],
                "match": [{"not": [{"path": CADDY_MATCH_STATIC_FILES}]}],
            },
            {
                "handle": [
                    {
                        "encodings": {"gzip": {}},
                        "handler": "encode",
                        "prefer": ["gzip"],
                    },
                    {
                        "handler": "file_server",
                        "hide": ["/etc/caddy/Caddyfile"],
                    },
                ]
            },
        ]

        return {
            "apps": {
                "http": {
                    "servers": {
                        "srv0": {
                            "listen": [":443"],
                            "routes": CADDY_ROUTES_SECURE,
                        },
                        "srv1": {
                            "listen": [":80"],
                            "routes": CADDY_ROUTES,
                        },
                    }
                },
                "tls": {
                    "automation": {
                        "policies": [
                            {
                                "issuers": [{"module": "internal"}],
                                # "subjects": ["stage.heimlicher.com.local"],
                                "subjects": [site_env_hostname],
                            }
                        ]
                    }
                },
            }
        }

    def apply_config(self, base_url, caddy_config):
        api_path = "load"
        response = self.api(base_url, api_path, method="POST", data=caddy_config)
        if response.get("message") != "OK":
            wrn(f"Failed to update Caddy configuration: {response}")

    @staticmethod
    def api(base_url, path="", method="POST", data=None):
        if data:
            data = json.dumps(data, indent=2).encode("utf-8")

        req = urllib.request.Request(
            urllib.parse.urljoin(base_url, path), data=data, method=method
        )
        req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req) as response:
                r = response.read().decode("utf-8")
                if response.status != 200:
                    return {
                        "message": f"Error HTTP Status {response.status}",
                        "path": path,
                    }
                return json.loads(r) if r else {"message": "OK", "path": path}

        except urllib.error.HTTPError as e:
            return {"message": str(e), "path": path}
        except json.decoder.JSONDecodeError as e:
            return {"message": str(e), "path": path}

        return {"message": "unknown error", "path": path}
