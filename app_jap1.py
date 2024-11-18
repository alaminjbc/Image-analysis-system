from flask import Flask, render_template_string, request, redirect, url_for, flash, session
import os
import PIL.Image
import google.generativeai as genai
from werkzeug.utils import secure_filename
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=1)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# Configure upload folder and allowed extensions
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'avif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Configure Google Generative AI
GOOGLE_API_KEY = "AIzaSyCrTiMRhKa1h2rVJLyg-5TXvcVQcGtQXk8"
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel(model_name="gemini-1.5-flash")

# Store analysis history
if not hasattr(app, 'analysis_history'):
    app.analysis_history = []

# HTML Templates
INDEX_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>画像分析システム</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.19/tailwind.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body class="bg-gray-100">
    <div class="flex h-screen">
        <!-- サイドバー -->
        <div class="w-64 bg-gray-800 text-white flex flex-col">
            <div class="p-4 border-b border-gray-700">
                <h1 class="text-xl font-bold">画像分析システム</h1>
            </div>
            <nav class="mt-4 flex-grow">
                <a href="{{ url_for('index') }}" 
                   class="flex items-center px-4 py-3 hover:bg-gray-700 {% if request.endpoint == 'index' %}bg-gray-700{% endif %}">
                    <i class="fas fa-home mr-3"></i>
                    ホーム
                </a>
                <a href="{{ url_for('history') }}" 
                   class="flex items-center px-4 py-3 hover:bg-gray-700 {% if request.endpoint == 'history' %}bg-gray-700{% endif %}">
                    <i class="fas fa-history mr-3"></i>
                    履歴
                </a>
            </nav>
            <div class="p-4 border-t border-gray-700">
                <p class="text-sm text-gray-400">バージョン 1.0</p>
            </div>
        </div>

        <!-- メインコンテンツ -->
        <div class="flex-1 overflow-auto">
            <div class="py-12 px-4 sm:px-6 lg:px-8">
                <div class="max-w-md mx-auto bg-white rounded-lg shadow-md p-6">
                    <h2 class="text-2xl font-bold text-center mb-8">財布分析ツール</h2>
                    
                    {% with messages = get_flashed_messages() %}
                        {% if messages %}
                            {% for message in messages %}
                                <div class="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative mb-4" role="alert">
                                    <span class="block sm:inline">{{ message }}</span>
                                </div>
                            {% endfor %}
                        {% endif %}
                    {% endwith %}

                    <form action="{{ url_for('upload_files') }}" method="post" enctype="multipart/form-data" class="space-y-6">
                        <div>
                            <label class="block text-sm font-medium text-gray-700 mb-2">
                                財布の画像をアップロード（前面、背面、内部、側面の4枚）
                            </label>
                            <input type="file" name="files[]" multiple accept=".png,.jpg,.jpeg,.webp,.avif" 
                                   class="w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500"
                                   required>
                        </div>
                        <button type="submit" class="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500">
                            分析開始
                        </button>
                    </form>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
'''

RESULTS_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>画像分析システム - 結果</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.19/tailwind.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body class="bg-gray-100">
    <div class="flex h-screen">
        <!-- サイドバー -->
        <div class="w-64 bg-gray-800 text-white flex flex-col">
            <div class="p-4 border-b border-gray-700">
                <h1 class="text-xl font-bold">画像分析システム</h1>
            </div>
            <nav class="mt-4 flex-grow">
                <a href="{{ url_for('index') }}" 
                   class="flex items-center px-4 py-3 hover:bg-gray-700">
                    <i class="fas fa-home mr-3"></i>
                    ホーム
                </a>
                <a href="{{ url_for('history') }}" 
                   class="flex items-center px-4 py-3 hover:bg-gray-700">
                    <i class="fas fa-history mr-3"></i>
                    履歴
                </a>
            </nav>
            <div class="p-4 border-t border-gray-700">
                <p class="text-sm text-gray-400">バージョン 1.0</p>
            </div>
        </div>

        <!-- メインコンテンツ -->
        <div class="flex-1 overflow-auto">
            <div class="py-12 px-4 sm:px-6 lg:px-8">
                <div class="max-w-3xl mx-auto bg-white rounded-lg shadow-md p-6">
                    <h2 class="text-2xl font-bold text-center mb-8">分析結果</h2>
                    
                    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {% set fields = [
                            ('製品カテゴリー', analysis.product_category),
                            ('ブランド', analysis.brand),
                            ('モデル', analysis.model),
                            ('サイズ区分', analysis.size_category),
                            ('形状区分', analysis.shape_category),
                            ('素材', analysis.material),
                            ('カラー', analysis.color),
                            ('製品状態', analysis.product_condition),
                            ('損傷箇所', analysis.damage_location),
                            ('シミ', analysis.stain),
                            ('シミの状態', analysis.stain_condition),
                            ('カビ', analysis.mold),
                            ('分析箇所', analysis.analyzed_area),
                            ('損傷部分', analysis.damaged_areas),
                            ('ジッパーの状態', analysis.zipper_condition),
                            ('留め具の状態', analysis.fastener_condition),
                            ('光沢の状態', analysis.vanish_status),
                            ('縫い目の状態', analysis.stitch_condition)
                        ] %}
                        
                        {% for label, value in fields %}
                        <div class="bg-gray-50 p-4 rounded-lg">
                            <label class="block text-sm font-medium text-gray-700 mb-1">{{ label }}</label>
                            <input type="text" value="{{ value }}" readonly 
                                   class="w-full px-3 py-2 bg-white border border-gray-300 rounded-md shadow-sm">
                        </div>
                        {% endfor %}
                    </div>
                    
                    <div class="mt-8 text-center">
                        <a href="{{ url_for('index') }}" 
                           class="inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500">
                            新しい分析を開始
                        </a>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
'''

HISTORY_TEMPLATE = '''
<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>画像分析システム - 履歴</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/tailwindcss/2.2.19/tailwind.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
</head>
<body class="bg-gray-100">
    <div class="flex h-screen">
        <!-- サイドバー -->
        <div class="w-64 bg-gray-800 text-white flex flex-col">
            <div class="p-4 border-b border-gray-700">
                <h1 class="text-xl font-bold">画像分析システム</h1>
            </div>
            <nav class="mt-4 flex-grow">
                <a href="{{ url_for('index') }}" 
                   class="flex items-center px-4 py-3 hover:bg-gray-700">
                    <i class="fas fa-home mr-3"></i>
                    ホーム
                </a>
                <a href="{{ url_for('history') }}" 
                   class="flex items-center px-4 py-3 hover:bg-gray-700 bg-gray-700">
                    <i class="fas fa-history mr-3"></i>
                    履歴
                </a>
            </nav>
            <div class="p-4 border-t border-gray-700">
                <p class="text-sm text-gray-400">バージョン 1.0</p>
            </div>
        </div>

        <!-- メインコンテンツ -->
        <div class="flex-1 overflow-auto">
            <div class="py-12 px-4 sm:px-6 lg:px-8">
                <div class="max-w-6xl mx-auto">
                    <h2 class="text-2xl font-bold text-center mb-8">分析履歴</h2>
                    
                    {% if history %}
                    <div class="bg-white shadow overflow-hidden sm:rounded-md">
                        <ul class="divide-y divide-gray-200">
                            {% for entry in history %}
                            <li>
                                <div class="px-4 py-4 sm:px-6">
                                    <div class="flex items-center justify-between">
                                        <div class="flex-1">
                                            <h3 class="text-lg font-medium text-gray-800">
                                                {{ entry.analysis.brand }} {{ entry.analysis.model }}
                                            </h3>
                                            <p class="mt-1 text-sm text-gray-600">
                                                分析日時: {{ entry.timestamp }}
                                            </p>
                                        </div>
                                        <div class="text-right text-sm">
                                            <p class="text-gray-600">状態: {{ entry.analysis.product_condition }}</p>
                                            <p class="text-gray-600">素材: {{ entry.analysis.material }}</p>
                                        </div>
                                    </div>
                                </div>
                            </li>
                            {% endfor %}
                        </ul>
                    </div>
                    {% else %}
                    <div class="text-center text-gray-600">
                        <p>分析履歴がありません</p>
                    </div>
                    {% endif %}
                </div>
            </div>
        </div>
    </div>
</body>
</html>
'''

class WalletAnalysis:
    def __init__(self):
        self.product_category = "財布"
        self.brand = "未指定"
        self.model = "未指定"
        self.size_category = "未指定"
        self.shape_category = "未指定"
        self.inquiry_info = "未指定"
        self.material = "未指定"
        self.color = "未指定"
        self.product_condition = "未指定"
        self.damage_location = "未指定"
        self.stain = "未指定"
        self.stain_condition = "未指定"
        self.mold = "未指定"
        self.factors = "未指定"
        self.analyzed_area = "未指定"
        self.damaged_areas = "未指定"
        self.zipper_condition = "未指定"
        self.fastener_condition = "未指定"
        self.vanish_status = "未指定"
        self.stitch_condition = "未指定"
    
    def update_attribute(self, attr_name, new_value):
        if new_value and new_value.strip() and new_value != "未指定":
            current_value = getattr(self, attr_name)
            if current_value == "未指定" or not current_value:
                setattr(self, attr_name, new_value.strip())
            elif new_value != current_value:
                if attr_name in ['damaged_areas', 'analyzed_area']:
                    current_set = set(current_value.split(', '))
                    new_set = set(new_value.split(', '))
                    setattr(self, attr_name, ', '.join(current_set.union(new_set)))
                elif 'damage' in new_value.lower() or 'severe' in new_value.lower():
                    setattr(self, attr_name, new_value.strip())

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def analyze_image(img_path, view_type):
    try:
        img = PIL.Image.open(img_path)
        logger.info(f"Successfully opened image: {img_path}")
        
        prompt = f"""
        財布の{view_type}ビューを分析中。各カテゴリーの値のみを提供してください:
        
        1. ブランド: (エルメス/ルイヴィトン/バレンシアガ/ボッテガヴェネタ/グッチ/シャネル/カルティエ/ミュウミュウ/その他)
        2. モデル: (標準モデルの場合)
        3. サイズ区分: (長財布/折りたたみ財布/コンパクト財布)
        4. 形状区分: (折りたたみ式/ジッパー付き折りたたみ式)
        5. 素材: (レザー/合成皮革/クロコダイルレザー)
        6. カラー: (オレンジ/グリーン/ブルー/クリーム/ライトブラウン/ブラック/ブラウン)
        7. 製品状態: (ひび割れ/表面剥離/光沢剥離/破れ)
        8. 損傷箇所: (全体的/外部のみ/内部のみ)
        9. シミ: (シミあり/シミなし)
        10. シミの状態: (該当なし/軽度のシミ/重度のシミ)
        11. カビ: (カビあり/カビなし)
        12. 分析箇所: (ジッパー/留め具/縫い目/光沢)
        13. 損傷部分: (留め具/金具/縫い目/光沢)
        14. ジッパーの状態: (損傷あり/損傷なし/錆びあり損傷なし)
        15. 留め具の状態: (損傷あり/損傷なし)
        16. 光沢の状態: (損傷なし/ひび割れまたは剥離あり)
        17. 縫い目の状態: (ほつれあり/ほつれなし)

        番号と値のみで回答してください:
        1: グッチ
        2: GGマーモント
        など
        """
        
        logger.info("Sending image to AI model for analysis")
        response = model.generate_content([prompt, img])
        logger.info("Received response from AI model")
        
        analysis = {}
        for line in response.text.strip().split('\n'):
            if ':' in line:
                number, value = line.split(':', 1)
                analysis[number.strip()] = value.strip()
        
        return analysis
    except Exception as e:
        logger.error(f"Error in analyze_image: {str(e)}")
        raise

@app.route('/')
def index():
    logger.info("Accessing home page")
    return render_template_string(INDEX_TEMPLATE)

@app.route('/history')
def history():
    logger.info("Accessing history page")
    return render_template_string(HISTORY_TEMPLATE, history=app.analysis_history)

@app.route('/upload', methods=['POST'])
def upload_files():
    try:
        logger.info("Starting file upload process")
        
        if 'files[]' not in request.files:
            logger.warning("No files found in request")
            flash('ファイルが選択されていません')
            return redirect(request.url)

        files = request.files.getlist('files[]')
        logger.info(f"Number of files received: {len(files)}")
        
        if len(files) != 4:
            logger.warning(f"Incorrect number of files: {len(files)}")
            flash('4枚の画像をアップロードしてください')
            return redirect(request.url)

        # Create upload folder if it doesn't exist
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        logger.info(f"Upload folder confirmed: {app.config['UPLOAD_FOLDER']}")
        
        uploaded_paths = []
        for i, file in enumerate(files):
            if file and allowed_file(file.filename):
                try:
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    uploaded_paths.append(file_path)
                    logger.info(f"Successfully saved file {i+1}: {filename}")
                except Exception as e:
                    logger.error(f"Error saving file {i+1}: {str(e)}")
                    raise

        if len(uploaded_paths) != 4:
            logger.warning("Not all files were successfully uploaded")
            flash('4枚の有効な画像ファイルをアップロードしてください')
            return redirect(request.url)

        # Process images and perform analysis
        combined_analysis = WalletAnalysis()
        views = ['前面', '背面', '内部', '側面']
        
        attr_map = {
            '1': 'brand', '2': 'model', '3': 'size_category',
            '4': 'shape_category', '5': 'material', '6': 'color',
            '7': 'product_condition', '8': 'damage_location',
            '9': 'stain', '10': 'stain_condition', '11': 'mold',
            '12': 'analyzed_area', '13': 'damaged_areas',
            '14': 'zipper_condition', '15': 'fastener_condition',
            '16': 'vanish_status', '17': 'stitch_condition'
        }

        try:
            logger.info("Starting image analysis")
            for i, (img_path, view) in enumerate(zip(uploaded_paths, views)):
                logger.info(f"Analyzing {view} image: {img_path}")
                analysis = analyze_image(img_path, view)
                logger.info(f"Analysis completed for {view}")
                
                for number, value in analysis.items():
                    if number in attr_map:
                        combined_analysis.update_attribute(attr_map[number], value)

            # Add to history
            app.analysis_history.insert(0, {
                'timestamp': datetime.now().strftime('%Y年%m月%d日 %H:%M:%S'),
                'analysis': combined_analysis
            })
            logger.info("Analysis history updated")

            # Keep only the last 50 analyses
            if len(app.analysis_history) > 50:
                app.analysis_history = app.analysis_history[:50]

        except Exception as e:
            logger.error(f"Error during analysis: {str(e)}")
            flash(f'分析中にエラーが発生しました: {str(e)}')
            return redirect(url_for('index'))
        
        finally:
            # Clean up uploaded files
            logger.info("Cleaning up uploaded files")
            for path in uploaded_paths:
                try:
                    if os.path.exists(path):
                        os.remove(path)
                        logger.info(f"Removed file: {path}")
                except Exception as e:
                    logger.error(f"Error removing file {path}: {str(e)}")

        logger.info("Analysis completed successfully")
        return render_template_string(RESULTS_TEMPLATE, analysis=combined_analysis)

    except Exception as e:
        logger.error(f"Unexpected error in upload_files: {str(e)}")
        flash('予期せぬエラーが発生しました。もう一度お試しください。')
        return redirect(url_for('index'))

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    logger.error(f"Page not found: {request.url}")
    return render_template_string('''
        <div class="min-h-screen flex items-center justify-center bg-gray-100">
            <div class="text-center">
                <h1 class="text-4xl font-bold text-gray-800 mb-4">404 - ページが見つかりません</h1>
                <p class="text-gray-600 mb-8">お探しのページは存在しないか、移動した可能性があります。</p>
                <a href="{{ url_for('index') }}" class="text-indigo-600 hover:text-indigo-800">
                    ホームページに戻る
                </a>
            </div>
        </div>
    '''), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {str(error)}")
    return render_template_string('''
        <div class="min-h-screen flex items-center justify-center bg-gray-100">
            <div class="text-center">
                <h1 class="text-4xl font-bold text-gray-800 mb-4">500 - サーバーエラー</h1>
                <p class="text-gray-600 mb-8">申し訳ありません。サーバーで問題が発生しました。</p>
                <a href="{{ url_for('index') }}" class="text-indigo-600 hover:text-indigo-800">
                    ホームページに戻る
                </a>
            </div>
        </div>
    '''), 500

if __name__ == '__main__':
    # Create uploads directory if it doesn't exist
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    
    # Set up logging for the development server
    if app.debug:
        logger.setLevel(logging.DEBUG)
        
    app.run(debug=True)