"""
中文分词RESTful API服务
使用Flask和jieba库提供中文文本分词功能

使用方法：
1. 安装依赖：pip install -r requirements.txt
2. 运行服务：python app.py
3. 调用API：POST http://localhost:5000/api/tokenize
"""

import logging
import json
import uuid
import time
from functools import wraps
from flask import Flask, request, jsonify
from flask.views import MethodView
from flask_cors import CORS
import jieba
from config import config

class RequestAdapter(logging.LoggerAdapter):
    """请求日志适配器，自动添加request_id"""
    def process(self, msg, kwargs):
        # 从请求上下文获取request_id，如果没有则使用默认值
        request_id = getattr(request, 'request_id', 'N/A') if request else 'N/A'
        return f"[{request_id}] {msg}", kwargs

# ===== 统一工具函数 =====

# 简单内存缓存（全局变量，将在应用启动时初始化）
_token_cache = {}
_cache_max_size = 1000  # 默认值，将在setup_logging中更新
_cache_hits = 0
_cache_misses = 0
_cache_enabled = True

def create_response(success=True, data=None, message=None, code=200):
    """
    创建统一格式的API响应

    Args:
        success (bool): 操作是否成功
        data (any): 响应数据
        message (str): 响应消息
        code (int): HTTP状态码

    Returns:
        tuple: (json_response, status_code)
    """
    response = {
        'success': success,
        'code': code,
        'timestamp': int(time.time())
    }

    if data is not None:
        response['data'] = data

    if message is not None:
        response['message'] = message

    return jsonify(response), code

def create_error_response(message, code=400, details=None):
    """
    创建统一格式的错误响应

    Args:
        message (str): 错误消息
        code (int): HTTP状态码
        details (any): 错误详情

    Returns:
        tuple: (json_response, status_code)
    """
    return create_response(
        success=False,
        message=message,
        code=code,
        data={'error_details': details} if details else None
    )

def get_cache_key(text, mode):
    """生成缓存键"""
    return f"{mode}:{hash(text)}"

def get_from_cache(cache_key):
    """从缓存获取结果"""
    global _cache_hits, _cache_misses
    if cache_key in _token_cache:
        _cache_hits += 1
        return _token_cache[cache_key]
    _cache_misses += 1
    return None

def set_cache(cache_key, tokens):
    """设置缓存"""
    global _cache_max_size
    if len(_token_cache) >= _cache_max_size:
        # 简单的LRU：删除第一个元素
        oldest_key = next(iter(_token_cache))
        del _token_cache[oldest_key]
    _token_cache[cache_key] = tokens

def validate_input_text(text):
    """
    验证输入文本

    Args:
        text (str): 输入文本

    Returns:
        tuple: (is_valid, error_message)
    """
    if not text or not isinstance(text, str):
        return False, "输入文本不能为空且必须是字符串"

    text = text.strip()
    if not text:
        return False, "输入文本不能为空白字符"

    # 长度限制（从配置获取）
    from config import get_config
    config_obj = get_config()
    max_length = config_obj.MAX_TEXT_LENGTH
    if len(text) > max_length:
        return False, f"文本长度不能超过{max_length}字符"

    # 基础内容检查（可根据需要扩展）
    if any(char.isspace() and not char.isspace() for char in text if ord(char) < 32):
        return False, "文本包含无效字符"

    return True, None

def request_id_logger():
    """为请求添加唯一ID的装饰器"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            request.request_id = str(uuid.uuid4())
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def log_request_info(func):
    """记录请求信息的装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        request_id = getattr(request, 'request_id', 'unknown')

        # 记录请求开始
        logging.info(f"[{request_id}] {request.method} {request.path} - 开始处理")

        try:
            result = func(*args, **kwargs)
            duration = time.time() - start_time

            # 记录请求完成
            if isinstance(result, tuple) and len(result) == 2:
                status_code = result[1]
            else:
                status_code = 200

            logging.info(f"[{request_id}] {request.method} {request.path} - 完成 "
                        f"(耗时: {duration:.3f}s, 状态码: {status_code})")

            return result
        except Exception as e:
            duration = time.time() - start_time
            logging.error(f"[{request_id}] {request.method} {request.path} - 错误 "
                         f"(耗时: {duration:.3f}s): {str(e)}")
            raise

    return wrapper

# 配置日志（优化版）
def setup_logging(app_config=None):
    """配置日志记录"""
    if app_config is None:
        from config import get_config
        app_config = get_config()

    # 验证配置
    app_config.validate_config()

    # 创建日志格式器
    formatter = logging.Formatter(app_config.LOG_FORMAT)

    # 清除现有处理器
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # 文件处理器
    try:
        file_handler = logging.FileHandler(app_config.LOG_FILE, encoding='utf-8')
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except Exception as e:
        logging.warning(f"无法创建日志文件 {app_config.LOG_FILE}: {e}")

    # 设置日志级别
    root_logger.setLevel(app_config.get_log_level())

    # 初始化缓存配置
    global _cache_max_size, _cache_enabled
    _cache_max_size = app_config.CACHE_MAX_SIZE
    _cache_enabled = app_config.CACHE_ENABLED

    logging.info(f"日志系统初始化完成，级别: {app_config.LOG_LEVEL}")
    logging.info(f"缓存配置 - 启用: {_cache_enabled}, 最大大小: {_cache_max_size}")

# 初始化jieba（优化版）
def setup_jieba(app_config=None):
    """初始化jieba分词器"""
    if app_config is None:
        from config import get_config
        app_config = get_config()

    # 加载自定义词典（如果配置了）
    if app_config.JIEBA_DICT_PATH:
        try:
            jieba.set_dictionary(app_config.JIEBA_DICT_PATH)
            logging.info(f"已加载自定义词典: {app_config.JIEBA_DICT_PATH}")
        except Exception as e:
            logging.warning(f"加载自定义词典失败: {e}")

    # 加载用户词典（如果配置了）
    if app_config.JIEBA_USER_DICT_PATH:
        try:
            jieba.load_userdict(app_config.JIEBA_USER_DICT_PATH)
            logging.info(f"已加载用户词典: {app_config.JIEBA_USER_DICT_PATH}")
        except Exception as e:
            logging.warning(f"加载用户词典失败: {e}")

    # 预热jieba（提高首次分词性能）
    try:
        jieba.cut("预热", cut_all=False)
        jieba.cut("预热", cut_all=True)  # 全模式预热
        jieba.cut_for_search("预热")
        logging.info("jieba分词器初始化完成并已预热")
    except Exception as e:
        logging.error(f"jieba预热失败: {e}")


# 分词核心函数（优化版）
def jieba_tokenize(text, mode='精确', use_cache=True):
    """
    使用jieba进行中文分词（支持缓存和输入验证）

    Args:
        text (str): 待分词文本
        mode (str): 分词模式 ('精确', '全模式', '搜索引擎')
        use_cache (bool): 是否使用缓存

    Returns:
        list: 分词结果列表

    Raises:
        ValueError: 输入验证失败或分词模式不支持
    """
    # 输入验证
    is_valid, error_msg = validate_input_text(text)
    if not is_valid:
        raise ValueError(error_msg)

    # 去除首尾空白字符
    text = text.strip()

    # 缓存检查
    if use_cache and _cache_enabled:
        cache_key = get_cache_key(text, mode)
        cached_result = get_from_cache(cache_key)
        if cached_result is not None:
            logging.debug(f"缓存命中: {cache_key}")
            return cached_result

    mode_mapping = {
        '精确': jieba.cut,
        '全模式': lambda text: jieba.cut(text, cut_all=True),
        '搜索引擎': jieba.cut_for_search
    }

    if mode not in mode_mapping:
        raise ValueError(f"不支持的分词模式: {mode}")

    # 执行分词
    cut_func = mode_mapping[mode]
    tokens = list(cut_func(text))

    # 过滤空白字符
    tokens = [token.strip() for token in tokens if token.strip()]

    # 设置缓存
    if use_cache and _cache_enabled and tokens:
        set_cache(cache_key, tokens)
        logging.debug(f"缓存设置: {cache_key}")

    return tokens

def get_cache_stats():
    """获取缓存统计信息"""
    total_requests = _cache_hits + _cache_misses
    hit_rate = (_cache_hits / total_requests * 100) if total_requests > 0 else 0
    return {
        'cache_size': len(_token_cache),
        'cache_hits': _cache_hits,
        'cache_misses': _cache_misses,
        'hit_rate': f"{hit_rate:.2f}%",
        'max_size': _cache_max_size
    }

# 创建Flask应用（优化版）
def create_app(config_name='default'):
    """应用工厂函数"""
    app = Flask(__name__)

    # 获取配置对象
    app_config = config[config_name]
    app.config.from_object(app_config)

    # 设置日志和jieba（使用配置对象）
    setup_logging(app_config)
    setup_jieba(app_config)

    # 根据配置启用CORS
    if app_config.ENABLE_CORS:
        CORS(app, resources={r"/api/*": {"origins": "*"}})
        logging.info("CORS已启用，允许所有源访问 /api/* 路径")

    # 注册路由
    register_routes(app)

    # 注册错误处理器
    register_error_handlers(app)

    # 应用启动日志
    logging.info(f"应用启动完成 - 环境: {config_name}, 调试模式: {app_config.DEBUG}")

    return app

# 注册路由
def register_routes(app):
    """注册API路由"""

    class TokenizeAPI(MethodView):
        """中文分词API视图（优化版）"""

        decorators = [log_request_info, request_id_logger()]

        def post(self):
            """处理分词请求"""
            try:
                # 获取请求数据
                data = request.get_json()
                if not data:
                    return create_error_response("请求体不能为空", 400)

                # 验证必需参数
                text = data.get('text')
                if not text:
                    return create_error_response("text参数不能为空", 400)

                # 获取分词模式，默认为精确模式
                mode = data.get('mode', '精确')

                # 执行分词
                tokens = jieba_tokenize(text, mode)

                # 返回结果
                result_data = {
                    'tokens': tokens,
                    'mode': mode,
                    'count': len(tokens),
                    'original_text': text,
                    'cache_stats': get_cache_stats()
                }

                return create_response(
                    success=True,
                    data=result_data,
                    message=f"成功处理分词请求，模式: {mode}, 词汇数: {len(tokens)}",
                    code=200
                )

            except ValueError as e:
                return create_error_response(str(e), 400)
            except Exception as e:
                logging.error(f"服务器内部错误: {str(e)}")
                return create_error_response("服务器内部错误", 500)

        def get(self):
            """获取API使用说明"""
            info = {
                'api_name': '中文分词API',
                'version': '1.1.0',  # 版本升级
                'description': '基于jieba库的中文文本分词服务（优化版）',
                'features': [
                    '支持三种分词模式',
                    '输入验证和长度限制',
                    '内存缓存提升性能',
                    '统一响应格式',
                    '请求追踪和日志记录'
                ],
                'endpoints': {
                    'POST /api/tokenize': {
                        'description': '执行中文分词',
                        'parameters': {
                            'text': '待分词文本（必需，最大10000字符）',
                            'mode': '分词模式（可选）：精确、全模式、搜索引擎'
                        },
                        'example': {
                            'request': {'text': '我爱北京天安门', 'mode': '精确'},
                            'response': {
                                'success': True,
                                'code': 200,
                                'timestamp': 1640995200,
                                'message': '成功处理分词请求，模式: 精确, 词汇数: 4',
                                'data': {
                                    'tokens': ['我', '爱', '北京', '天安门'],
                                    'mode': '精确',
                                    'count': 4,
                                    'original_text': '我爱北京天安门',
                                    'cache_stats': {
                                        'cache_size': 1,
                                        'cache_hits': 0,
                                        'cache_misses': 1,
                                        'hit_rate': '0.00%',
                                        'max_size': 1000
                                    }
                                }
                            }
                        }
                    }
                },
                'supported_modes': ['精确', '全模式', '搜索引擎'],
                'limitations': {
                    'max_text_length': 10000,
                    'cache_size': 1000,
                    'supported_encoding': 'UTF-8'
                }
            }
            return create_response(
                success=True,
                data=info,
                message="API信息获取成功",
                code=200
            )

    # 注册API路由
    tokenize_view = TokenizeAPI.as_view('tokenize_api')
    app.add_url_rule('/api/tokenize', view_func=tokenize_view, methods=['GET', 'POST'])

    # 根路径重定向到API说明
    @app.route('/')
    def index():
        return jsonify({
            'message': '中文分词API服务',
            'version': '1.0.0',
            'endpoints': {
                'api': '/api/tokenize',
                'docs': '/api/tokenize (GET)'
            }
        })

# 注册错误处理器（优化版）
def register_error_handlers(app):
    """注册全局错误处理器"""

    @app.errorhandler(400)
    def bad_request(error):
        return create_error_response("请求参数错误", 400, str(error))

    @app.errorhandler(404)
    def not_found(error):
        return create_error_response("请求的资源不存在", 404, str(error))

    @app.errorhandler(405)
    def method_not_allowed(error):
        return create_error_response("请求方法不被允许", 405, str(error))

    @app.errorhandler(413)
    def payload_too_large(error):
        return create_error_response("请求体过大", 413, str(error))

    @app.errorhandler(500)
    def internal_error(error):
        request_id = getattr(request, 'request_id', 'unknown')
        logging.error(f"[{request_id}] 服务器内部错误: {error}")
        return create_error_response("服务器内部错误", 500)

    @app.errorhandler(Exception)
    def handle_exception(error):
        """处理未捕获的异常"""
        request_id = getattr(request, 'request_id', 'unknown')
        logging.error(f"[{request_id}] 未处理的异常: {error}", exc_info=True)
        return create_error_response("服务器遇到未知错误", 500)

# 主函数
if __name__ == '__main__':
    app = create_app('development')
    app.run(host='0.0.0.0', port=5000, debug=True)