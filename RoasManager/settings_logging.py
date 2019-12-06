import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} | {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} | {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
        'file_info': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'formatter': 'verbose',
            'filename': BASE_DIR + '/log/info.log',
            'encoding': 'UTF-8'
        },
        'file_error': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'formatter': 'verbose',
            'filename': BASE_DIR + '/log/error.log',
            'encoding': 'UTF-8',
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            'formatter': 'verbose',
            'include_html': True,
        }
    },
    'loggers': {
        'django': {
            'handlers': ['file_error', 'mail_admins'],
            'level': 'WARNING',
            'propagate': True,
        },
        'roas_manager': {
            'handlers': ['console', 'file_info', 'file_error', 'mail_admins'],
            'level': 'INFO',
            'propagate': True,
        },
        'users': {
            'handlers': ['console', 'file_info', 'file_error', 'mail_admins'],
            'level': 'INFO',
            'propagate': True,
        }
    }
}