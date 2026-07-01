'use client';

import { ref, uploadString, getDownloadURL, deleteObject } from 'firebase/storage';
import { storage } from './firebase';

export async function uploadFaceImage(
  uid: string,
  base64Image: string
): Promise<string> {
  const storageRef = ref(storage, `faces/${uid}/${Date.now()}.jpg`);
  await uploadString(storageRef, base64Image, 'data_url');
  return getDownloadURL(storageRef);
}

export async function deleteFaceImage(uid: string): Promise<void> {
  const storageRef = ref(storage, `faces/${uid}`);
  await deleteObject(storageRef);
}
