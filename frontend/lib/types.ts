export interface StudentData {
  id?: string;
  uid: string;
  email: string;
  name: string;
  rollNumber: string;
  department: string;
  year: string;
  semester: string;
  faceImageBase64: string;
  registeredAt: string;
}

export interface AttendanceRecord {
  id?: string;
  studentUid: string;
  studentName?: string;
  name?: string;
  rollNumber: string;
  rollNo?: string;
  department?: string;
  year?: string;
  semester?: string;
  timestamp: any;
  method: 'individual_live' | 'doorway_batch' | 'cctv_stream' | 'upload';
}

export interface UserProfile {
  uid: string;
  email: string;
  displayName?: string;
  role: 'admin' | 'student';
  createdAt: string;
}

export interface FaceMatch {
  uid: string;
  name: string;
  roll_no: string;
  distance: number;
}

export interface FaceDetectionResult {
  box: [number, number, number, number];
  match: FaceMatch | null;
}

export interface DetectWebcamResponse {
  faces_detected: number;
  frame_width: number;
  frame_height: number;
  face_data: FaceDetectionResult[];
}

export interface VerifyResponse {
  match: boolean;
  confidence: number;
  reason: string;
  distance: number;
}

export interface CCTVDetectResponse {
  faces_detected: number;
  face_data: CCTVFaceData[];
  frame_width: number;
  frame_height: number;
}

export interface CCTVFaceData {
  box: [number, number, number, number];
  has_encoding: boolean;
  bbox?: [number, number, number, number];
}

export interface CCTVProcessedFace {
  box: [number, number, number, number];
  has_encoding: boolean;
  frame_width: number;
  frame_height: number;
  student: StudentData | null;
}

export interface WebcamUIDetection {
  box: { x: number; y: number; width: number; height: number };
  isRecognized: boolean;
  student: FaceMatch | null;
}

export interface SyncStudentData {
  uid: string;
  name: string;
  roll_no: string;
  image_base64: string;
}

export interface AttendanceLogPayload {
  studentUid: string;
  studentName: string;
  rollNo: string;
  timestamp: any;
  method: AttendanceRecord['method'];
}
