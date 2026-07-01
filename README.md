# FaceSnap

AI-powered facial recognition attendance system for educational institutions. Combines a **Next.js 15** web frontend with a **FastAPI** backend using FaceNet + YOLO for real-time face detection and verification.

## Architecture

```
facesnap/
├── frontend/                  # Next.js 15 (React 19, TypeScript)
│   ├── app/                   # App Router pages & layouts
│   │   ├── about/             # About page
│   │   ├── attendance/        # Attendance records & logs
│   │   ├── cctv/              # IP camera / CCTV monitoring
│   │   ├── classroom/         # Batch doorway attendance
│   │   ├── contact/           # Contact / support form
│   │   ├── register/          # Student facial registration
│   │   ├── student/           # Live identity verification
│   │   ├── error.tsx          # Global error boundary
│   │   ├── globals.css        # Tailwind v4 + custom utilities
│   │   ├── layout.tsx         # Root layout (Nav, Footer, Chatbot)
│   │   ├── loading.tsx        # Global loading state
│   │   ├── not-found.tsx      # 404 page
│   │   └── page.tsx           # Landing / dashboard
│   ├── components/            # Shared UI
│   │   ├── AuthProvider.tsx   # Firebase Auth context + Firestore profile
│   │   ├── Chatbot.tsx        # AI assistant (Groq API)
│   │   ├── ChatbotWrapper.tsx # Client-only dynamic import wrapper
│   │   ├── ErrorBoundary.tsx  # React error boundary
│   │   ├── Footer.tsx         # Site footer
│   │   └── Navigation.tsx     # Top navigation bar
│   ├── hooks/                 # Custom React hooks
│   │   └── use-mobile.ts      # Responsive breakpoint detection
│   ├── lib/                   # Utilities & config
│   │   ├── firebase.ts        # Firebase init (lazy, SSR-safe)
│   │   ├── firestore-error.ts # Human-readable Firestore errors
│   │   ├── storage.ts         # Firebase Storage helpers
│   │   ├── types.ts           # TypeScript interfaces
│   │   └── utils.ts           # Misc helpers
│   ├── public/                # Static assets
│   │   ├── robots.txt         # SEO
│   │   └── .gitkeep
│   ├── .env.local             # Local environment (gitignored)
│   ├── next.config.ts         # Next.js config (standalone output)
│   ├── tsconfig.json          # TypeScript config
│   ├── firestore.rules        # Firestore security rules
│   ├── package.json           # Frontend dependencies
│   └── postcss.config.mjs     # PostCSS / Tailwind config
├── backend/                   # FastAPI Python server
│   ├── app/                   # Application package
│   │   ├── __init__.py
│   │   ├── config.py          # Thresholds, host, CORS settings
│   │   ├── main.py            # FastAPI entry point, CORS, routers
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   └── schemas.py     # Pydantic request/response models
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── detection.py   # /api/sync, /api/detect_webcam
│   │   │   ├── pi_routes.py   # /api/pi/stream, /api/pi/capture, /api/pi/detect
│   │   │   └── verification.py# /api/verify endpoint
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── camera.py      # Raspberry Pi camera controller
│   │       └── face_service.py# FaceNet embeddings + YOLO detection
│   ├── desktop_app.py         # Legacy Tkinter desktop app (standalone)
│   ├── requirements.txt       # Python dependencies
│   └── yolov8n.pt             # Pre-trained YOLO weights
├── .env.example               # Environment variable template
├── .gitignore                 # Comprehensive ignore rules
├── package.json               # Monorepo workspace scripts
└── README.md                  # This file
```

## Quick Start

### Prerequisites

- **Node.js** 20+ and **npm**
- **Python** 3.11+
- **Firebase project** with Firestore, Authentication, and Storage enabled
- **Groq API key** (free, no credit card) for the AI chatbot — get one at [console.groq.com](https://console.groq.com)

### Setup

```bash
# 1. Clone and install frontend dependencies
cd frontend && npm install

# 2. Install backend dependencies
cd ../backend
python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt

# 3. Configure environment
cp ../.env.example ../frontend/.env.local
# Edit frontend/.env.local with your Firebase project config & Groq API key
```

### Run

```bash
# Terminal 1 — Backend API server
cd backend
python -m uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend dev server
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The API is at [http://localhost:8000](http://localhost:8000).

## Environment Variables

Copy `.env.example` to `frontend/.env.local` and fill in the values.

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_GROQ_API_KEY` | Yes (chatbot) | Groq API key for AI assistant — get free at [console.groq.com](https://console.groq.com) |
| `NEXT_PUBLIC_AI_MODEL` | No | Groq model (default: `llama-3.3-70b`). Options: `llama-3.1-70b`, `llama-3.1-8b`, `mixtral-8x7b`, `gemma2-9b` |
| `NEXT_PUBLIC_APP_URL` | No | Frontend URL (default: `http://localhost:3000`) |
| `NEXT_PUBLIC_FIREBASE_PROJECT_ID` | **Yes** | Firebase project ID |
| `NEXT_PUBLIC_FIREBASE_APP_ID` | **Yes** | Firebase Web App ID |
| `NEXT_PUBLIC_FIREBASE_API_KEY` | **Yes** | Firebase Web API key |
| `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN` | **Yes** | Auth domain (`<project>.firebaseapp.com`) |
| `NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET` | **Yes** | Storage bucket (`<project>.firebasestorage.app`) |
| `NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID` | **Yes** | Sender ID from Firebase Console |
| `NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID` | No | Google Analytics measurement ID |
| `NEXT_PUBLIC_BACKEND_URL` | **Yes** | Backend API URL (default: `http://localhost:8000`) |

## Tech Stack

### Frontend

| Technology | Version | Purpose |
|------------|---------|---------|
| Next.js | 15.4+ | React framework with App Router |
| React | 19.2+ | UI library |
| TypeScript | 5.9+ | Type safety |
| Tailwind CSS | 4.1 | Utility-first styling |
| Firebase SDK | 12.11 | Auth, Firestore, Storage |
| motion | 12.23 | Animations (successor to framer-motion) |
| lucide-react | 0.553 | Icon library |
| react-webcam | 7.2 | Browser webcam capture |
| react-markdown | 10.1 | Chatbot message rendering |
| sonner | 2.0 | Toast notifications |
| class-variance-authority | 0.7 | Component variants |

### Backend

| Technology | Purpose |
|------------|---------|
| FastAPI | Web framework |
| TensorFlow / Keras-FaceNet | Face embedding generation |
| Ultralytics YOLOv8 | Face detection |
| OpenCV | Image processing |
| scipy | Distance computation for face matching |
| Uvicorn | ASGI server |

### AI / Computer Vision

- **Face Detection**: YOLOv8n (ultralytics) — lightweight, real-time face bounding box detection
- **Face Recognition**: Keras-FaceNet — generates 128-dimensional face embeddings for identity matching
- **AI Chatbot**: Groq API — free inference for Llama 3 / Mixtral / Gemma models (no credit card needed)
- **Backward Compatibility**: Legacy `desktop_app.py` uses `face_recognition` (dlib) for the standalone Tkinter app

## API Endpoints

All endpoints are served from `http://localhost:8000`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | API health check |
| POST | `/api/verify` | Verify a face image against enrolled students |
| POST | `/api/sync` | Sync student face data (base64) to backend memory |
| POST | `/api/detect_webcam` | Detect & recognize faces in a webcam frame |
| GET | `/api/pi/stream` | Raspberry Pi camera MJPEG stream |
| POST | `/api/pi/capture` | Capture a still from Pi camera |
| POST | `/api/pi/detect` | Detect faces on Pi camera feed |

### Backend Configuration (`backend/app/config.py`)

| Setting | Default | Description |
|---------|---------|-------------|
| `RECOGNITION_THRESHOLD` | 0.85 | Euclidean distance threshold for face matching |
| `YOLO_CONFIDENCE` | 0.3 | Minimum confidence for YOLO detection |
| `FACENET_INPUT_SIZE` | (160, 160) | Input image size for FaceNet model |
| `HOST` | 0.0.0.0 | Server bind address |
| `PORT` | 8000 | Server port |
| `CORS_ORIGINS` | * | Allowed CORS origins (comma-separated) |

## Pages & Routing

| Route | Auth Required | Description |
|-------|---------------|-------------|
| `/` | No | Landing page / dashboard with feature overview |
| `/register` | Yes | Register a new student with facial image capture |
| `/student` | Yes | Live one-on-one facial identity verification |
| `/classroom` | Yes | Batch doorway attendance for multiple students |
| `/cctv` | Yes | IP camera / CCTV-based monitoring and detection |
| `/attendance` | Yes | View attendance records and history |
| `/contact` | No | Contact / inquiry form |
| `/about` | No | About the project |

## Firebase Data Model

### Firestore Collections

#### `users/{uid}`
Stores user profile and role.

```typescript
{
  uid: string;          // Firebase Auth UID
  email: string;        // User email
  displayName?: string; // Optional display name
  role: "admin" | "student";
  createdAt: string;    // ISO 8601 date string
}
```

#### `students/{studentId}`
Stores enrolled student profiles with facial data.

```typescript
{
  uid: string;
  email: string;
  name: string;
  rollNumber: string;
  department: string;
  year: string;
  semester: string;
  faceImageBase64: string; // Backward-compatible base64 image
  registeredAt: string;    // ISO 8601
}
```

#### `attendance/{attendanceId}`
Stores attendance log entries.

```typescript
{
  studentUid: string;
  name: string;
  rollNumber: string;
  department: string;
  year: string;
  semester: string;
  timestamp: string;   // ISO 8601
  method: "individual_live" | "doorway_batch" | "cctv_stream" | "upload";
}
```

### Firebase Storage

Face images are uploaded to `gs://<bucket>/faces/<uid>.jpg` for efficient retrieval and to avoid Firestore's 1 MiB document size limit. The `lib/storage.ts` module provides `uploadFaceImage()` and `deleteFaceImage()` helpers.

### Security Rules

Firestore rules enforce:
- **Users**: Own profile read/write; admins can read/delete all
- **Students**: Authenticated read; owner write; admin/owner delete
- **Attendance**: Authenticated read; create by owner or admin; no updates; admin delete

Rules are defined in `frontend/firestore.rules` — deploy via:
```bash
firebase deploy --only firestore:rules
```

## Deployment

### Frontend (Vercel / any Node.js host)

```bash
cd frontend
NEXT_PUBLIC_GROQ_API_KEY=... npm run build
# Deploy the .next/standalone output
```

The `next.config.ts` is pre-configured with `output: 'standalone'` for deployment.

### Backend (any Python host)

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Monorepo Scripts

From the root directory:

| Command | Description |
|---------|-------------|
| `npm run dev` | Start frontend dev server |
| `npm run build` | Build frontend for production |
| `npm run start` | Start frontend production server |
| `npm run lint` | Run ESLint on frontend |
| `npm run backend` | Start backend API server with auto-reload |
| `npm run setup` | Install both frontend and backend dependencies |

## Legacy Desktop App

`backend/desktop_app.py` is a standalone Tkinter-based attendance application using `face_recognition` (dlib). It is independent of the web stack and can be run directly:
```bash
python backend/desktop_app.py
```
Requires `face-recognition` (dlib) which must be compiled with a C++ toolchain.

## License

MIT
# FaceSnap
