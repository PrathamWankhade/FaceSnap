'use client';

import { ref, uploadString, getDownloadURL, deleteObject, listAll } from 'firebase/storage';
import { storage } from './firebase';

export async function uploadFaceImage(
  uid: string,
  base64Image: string
): Promise<string> {
  const storageRef = ref(storage, `faces/${uid}/${Date.now()}.jpg`);
  await uploadString(storageRef, base64Image, 'data_url');
  return getDownloadURL(storageRef);
}

export async function deleteAllFaceImages(uid: string): Promise<void> {
  // listAll + delete each object: deleting the prefix alone is not recursive.
  const prefix = ref(storage, `faces/${uid}`);
  const listing = await listAll(prefix);
  await Promise.all([
    ...listing.items.map((item) => deleteObject(item)),
    ...listing.prefixes.map(async (sub) => {
      const subListing = await listAll(sub);
      await Promise.all(subListing.items.map((item) => deleteObject(item)));
    }),
  ]);
}

/** @deprecated Use deleteAllFaceImages instead (prefix delete is not recursive). */
export async function deleteFaceImage(uid: string): Promise<void> {
  return deleteAllFaceImages(uid);
}
