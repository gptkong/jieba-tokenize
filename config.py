import os
import logging

class Config:
    """应用配置类（优化版）"""

    # 基础配置
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', '16777216'))  # 16MB

    # jieba 配置
    JIEBA_DICT_PATH = os.environ.get('JIEBA_DICT_PATH')  # 自定义词典路径
    JIEBA_USER_DICT_PATH = os.environ.get('JIEBA_USER_DICT_PATH')  # 用户词典路径

    # API 配置
    API_VERSION = os.environ.get('API_VERSION', 'v1')
    DEFAULT_TOKENIZE_MODE = os.environ.get('DEFAULT_TOKENIZE_MODE', '精确')

    # 缓存配置
    CACHE_MAX_SIZE = int(os.environ.get('CACHE_MAX_SIZE', '1000'))
    CACHE_ENABLED = os.environ.get('CACHE_ENABLED', 'true').lower() == 'true'

    # 文本处理配置
    MAX_TEXT_LENGTH = int(os.environ.get('MAX_TEXT_LENGTH', '10000'))
    MIN_TEXT_LENGTH = int(os.environ.get('MIN_TEXT_LENGTH', '1'))

    # 日志配置
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'jieba_tokenize.log')
    LOG_FORMAT = os.environ.get('LOG_FORMAT',
                               '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # 性能配置
    REQUEST_TIMEOUT = int(os.environ.get('REQUEST_TIMEOUT', '30'))  # 秒
    WORKER_PROCESSES = int(os.environ.get('WORKER_PROCESSES', '4'))

    # 安全配置
    ENABLE_CORS = os.environ.get('ENABLE_CORS', 'false').lower() == 'true'
    RATE_LIMIT = os.environ.get('RATE_LIMIT', '100')  # 每分钟请求数

    # 数据库配置
    DB_PATH = os.environ.get('DB_PATH', 'jieba_stats.db')

    # 支持的分词模式
    TOKENIZE_MODES = {
        '精确': 'cut',
        '全模式': 'cut_all',
        '搜索引擎': 'cut_for_search'
    }

    @classmethod
    def validate_config(cls):
        """验证配置的有效性"""
        errors = []

        # 验证数值范围
        if cls.MAX_TEXT_LENGTH <= 0 or cls.MAX_TEXT_LENGTH > 1000000:
            errors.append("MAX_TEXT_LENGTH 必须在 1-1000000 之间")

        if cls.CACHE_MAX_SIZE <= 0 or cls.CACHE_MAX_SIZE > 10000:
            errors.append("CACHE_MAX_SIZE 必须在 1-10000 之间")

        if cls.DEFAULT_TOKENIZE_MODE not in cls.TOKENIZE_MODES:
            errors.append(f"DEFAULT_TOKENIZE_MODE 必须是: {list(cls.TOKENIZE_MODES.keys())}")

        # 验证日志级别
        valid_log_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if cls.LOG_LEVEL not in valid_log_levels:
            errors.append(f"LOG_LEVEL 必须是: {valid_log_levels}")

        if errors:
            raise ValueError(f"配置验证失败: {'; '.join(errors)}")

        return True

    @classmethod
    def get_log_level(cls):
        """获取日志级别对象"""
        return getattr(logging, cls.LOG_LEVEL.upper(), logging.INFO)

class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'
    CACHE_ENABLED = True
    ENABLE_CORS = True

class TestingConfig(Config):
    """测试环境配置"""
    TESTING = True
    DEBUG = True
    CACHE_ENABLED = False  # 测试时禁用缓存
    LOG_LEVEL = 'DEBUG'
    MAX_TEXT_LENGTH = 1000  # 测试时限制文本长度

class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False
    LOG_LEVEL = 'INFO'
    CACHE_ENABLED = True
    ENABLE_CORS = False

    # 生产环境必须有SECRET_KEY
    def __init__(self):
        if not os.environ.get('SECRET_KEY'):
            raise ValueError("生产环境必须设置 SECRET_KEY 环境变量")

# 配置字典
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

def get_config():
    """获取当前配置"""
    env = os.environ.get('FLASK_ENV', 'default')
    return config.get(env, config['default'])