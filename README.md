# Parallel Spreadsheet AI Processor

نظام احترافي لمعالجة صفوف `Excel/CSV` بالتوازي باستخدام نماذج ذكاء اصطناعي متعددة (خصوصًا عبر `OpenRouter`) مع كتابة النتائج في نفس الصفوف، ودعم تقسيم الإخراج إلى عدة أعمدة.

## المميزات

- تنفيذ متوازي للصفوف (`asyncio` + worker pool)
- واجهة عربية واضحة بالأيقونات (`/`)
- اختيار المزود: `OpenRouter` / `OpenAI` / `OpenAI-compatible` / `mock`
- تحميل قائمة نماذج OpenRouter تلقائيًا داخل الواجهة واختيار النموذج من القائمة
- دعم تعليمات ثابتة أو تعليمات لكل صف أو هجينة
- دعم اختيار النموذج لكل صف عبر `model_column`
- قراءة وكتابة `xlsx` و `csv`
- كتابة `status`, `error`, `output_raw` في نفس الصف
- تقسيم الإخراج:
  - `none`
  - `json` (توسيع تلقائي إلى أعمدة)
  - `delimiter` (مثل `||`)
- استئناف عملي عبر `skip_completed`
- واجهة API جاهزة للاستخدام من أي واجهة أمامية

## التشغيل

### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

### Windows (PowerShell)

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

افتح Swagger:

- [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## مثال سريع (بدون API خارجي) باستخدام `mock`

أنشئ ملف CSV مثل:

```csv
id,text,instructions
1,"هذا تعليق عميل","أعد JSON يحتوي summary وcategory"
2,"الخدمة ممتازة ولكن السعر مرتفع","أعد JSON يحتوي summary وcategory"
```

ثم استدعِ `POST /jobs/run-path` بهذا المثال:

```json
{
  "file_path": "/ABSOLUTE/PATH/sample.csv",
  "config": {
    "input": {
      "input_columns": ["text"]
    },
    "prompt": {
      "instruction_mode": "per_row",
      "instruction_column": "instructions",
      "user_template": "{instruction}\n\nالبيانات:\n{input}\n\nأعد الإخراج JSON فقط."
    },
    "model": {
      "provider": "mock",
      "model": "mock-1"
    },
    "concurrency": {
      "global_concurrency": 10,
      "provider_concurrency": 10
    },
    "rows": {
      "status_column": "status",
      "error_column": "error",
      "raw_output_column": "output_raw",
      "skip_completed": true
    },
    "output": {
      "split_mode": "json",
      "strict_parse": false
    }
  }
}
```

ملف جاهز مطابق تقريبًا:

- `/Users/majd/Desktop/codex/examples/mock_per_row_json_config.json`

## مثال إعداد احترافي لـ OpenRouter

ضع المفتاح في `.env`:

```env
OPENROUTER_API_KEY=...
OPENROUTER_HTTP_REFERER=http://localhost
OPENROUTER_APP_TITLE=Parallel Spreadsheet AI
```

ثم:

```json
{
  "file_path": "/ABSOLUTE/PATH/customers.xlsx",
  "config": {
    "input": {
      "input_columns": ["customer_comment", "product_name"],
      "include_column_labels": true
    },
    "prompt": {
      "instruction_mode": "fixed",
      "fixed_instruction": "حلل النص وأعد JSON فقط يحتوي المفاتيح: summary, sentiment, topic, priority",
      "system_prompt": "أنت محلل بيانات أعمال. لا تضف أي شرح خارج JSON.",
      "user_template": "{instruction}\n\nالبيانات:\n{input}"
    },
    "model": {
      "provider": "openrouter",
      "model": "openai/gpt-4.1-mini",
      "temperature": 0.1,
      "retries": 2,
      "timeout_seconds": 90
    },
    "concurrency": {
      "global_concurrency": 30,
      "provider_concurrency": 15
    },
    "rows": {
      "sheet_name": "Sheet1",
      "start_row": 2,
      "status_column": "status",
      "error_column": "error",
      "raw_output_column": "output_raw",
      "skip_completed": true
    },
    "output": {
      "split_mode": "json",
      "strict_parse": false,
      "json_prefix": ""
    }
  }
}
```

ملف جاهز:

- `/Users/majd/Desktop/codex/examples/openrouter_fixed_json_config.json`

## أوضاع التعليمات

- `fixed`: تعليمات ثابتة (`fixed_instruction`)
- `per_row`: تعليمات من عمود لكل صف (`instruction_column`)
- `hybrid`: دمج تعليمات ثابتة + تعليمات الصف
- `first_row_as_fixed`: يأخذ أول قيمة غير فارغة من عمود التعليمات ويطبقها على جميع الصفوف

## تقسيم الإخراج إلى أعمدة

### 1) JSON (أفضل خيار)

اطلب من النموذج الإرجاع بصيغة JSON فقط:

```json
{"summary":"...", "sentiment":"positive", "score": 8}
```

سيقوم النظام بإضافة أعمدة تلقائيًا مثل:

- `summary`
- `sentiment`
- `score`

### 2) Delimiter

إذا كان الإخراج:

`عنوان || تصنيف || ملاحظات`

اضبط:

```json
{
  "split_mode": "delimiter",
  "delimiter": "||",
  "output_columns": ["title", "category", "notes"]
}
```

## ملاحظات Numbers

يمكن استخدام Apple Numbers عبر:

1. التصدير إلى `xlsx` أو `csv`
2. تشغيل المعالجة
3. فتح الملف الناتج أو استيراده مرة أخرى

## ملاحظات Windows

- النظام نفسه يعمل على ويندوز لأن الكود مبني على `Python + FastAPI + pandas + pathlib` (بدون اعتماد على أوامر نظام داخل التطبيق).
- عند استخدام `POST /jobs/run-path` في JSON على ويندوز:
  - استخدم مسارًا مثل `C:/data/file.xlsx` (أسهل)
  - أو اهرب الشرطات العكسية: `C:\\data\\file.xlsx`
- إذا أردت تجنب المسارات تمامًا، استخدم `POST /jobs/run-file` وارفع الملف مباشرة.

## واجهات API الأساسية

- `GET /health`
- `GET /providers/presets`
- `GET /providers/openrouter/models`
- `POST /jobs/run-file`
- `POST /jobs/run-path`
- `GET /jobs`
- `GET /jobs/{job_id}`
- `POST /jobs/{job_id}/cancel`
- `GET /jobs/{job_id}/download`

## المخرجات المتقدمة (جديد)

يمكنك الآن تحديد مكان كتابة المخرجات داخل Excel من الواجهة أو عبر JSON:

- `output.output_file_name`: اسم ملف الإخراج
- `output.target_sheet_name`: اسم ورقة الإخراج
- `output.target_start_row`: صف بداية الكتابة (صف العناوين إذا كان `write_headers=true`)
- `output.target_start_column`: عمود البداية (`H` أو `8`)
- `output.export_columns`: الأعمدة التي تريد تصديرها فقط (مثل `status,error,summary`)

إذا لم تحدد هذه الخيارات، سيبقى السلوك الافتراضي كما هو (كتابة الملف الناتج بالشكل الكامل).
