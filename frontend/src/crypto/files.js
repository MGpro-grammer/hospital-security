/**
 * @file Chiffrement en enveloppe des fichiers du dossier medical.
 *
 * Principe : chaque fichier a sa PROPRE cle de donnees (DEK) en AES-256-GCM.
 * Le fichier n'est chiffre et stocke qu'une fois. Le partage se fait en
 * chiffrant la DEK avec la cle publique RSA de chaque ayant droit.
 *
 *   fichier ---[DEK]---> bloc chiffre (stocke une fois)
 *      DEK ---[RSA publique du patient]---> WrappedKey 1
 *      DEK ---[RSA publique du medecin]---> WrappedKey 2
 *
 * Pourquoi pas du RSA directement sur le fichier : RSA-2048 ne chiffre que
 * ~190 octets et reste lent. AES chiffre vite et sans limite de taille.
 */

import { bufToB64, b64ToBuf } from './keys.js'

/**
 * Genere une cle de donnees propre a UN fichier.
 * Extractible : elle doit pouvoir etre exportee pour etre chiffree.
 * @returns {Promise<CryptoKey>}
 */
export async function generateDek() {
    return crypto.subtle.generateKey({ name: 'AES-GCM', length: 256 }, true, [
        'encrypt',
        'decrypt',
    ])
}

/**
 * Chiffre un document COMPLET : nom, date et contenu en un seul bloc.
 *
 * health.pdf classe les trois comme sensibles. Les mettre dans le meme bloc
 * garantit que le serveur ne peut rien en apprendre, pas meme le nom.
 *
 * @param {{filename: string, examDate: string, content: ArrayBuffer}} doc
 * @param {CryptoKey} dek
 * @returns {Promise<{iv: string, ciphertext: string}>}
 */
export async function encryptDocument(doc, dek) {
    const payload = new TextEncoder().encode(
        JSON.stringify({
            filename: doc.filename,
            examDate: doc.examDate,
            content: bufToB64(doc.content),
        }),
    )
    const iv = crypto.getRandomValues(new Uint8Array(12))
    const ct = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, dek, payload)
    return { iv: bufToB64(iv), ciphertext: bufToB64(ct) }
}

/**
 * Dechiffre un document et restitue ses trois parties.
 * @param {{iv: string, ciphertext: string}} blob
 * @param {CryptoKey} dek
 * @returns {Promise<{filename: string, examDate: string, content: ArrayBuffer}>}
 */
export async function decryptDocument(blob, dek) {
    const plain = await crypto.subtle.decrypt(
        { name: 'AES-GCM', iv: b64ToBuf(blob.iv) },
        dek,
        b64ToBuf(blob.ciphertext),
    )
    const doc = JSON.parse(new TextDecoder().decode(plain))
    return {
        filename: doc.filename,
        examDate: doc.examDate,
        content: b64ToBuf(doc.content),
    }
}

/**
 * Chiffre la DEK avec la cle publique RSA d'un ayant droit.
 * @param {CryptoKey} dek
 * @param {CryptoKey} publicKey
 * @returns {Promise<string>} DEK chiffree, base64.
 */
export async function wrapDek(dek, publicKey) {
    const raw = await crypto.subtle.exportKey('raw', dek)
    return bufToB64(await crypto.subtle.encrypt({ name: 'RSA-OAEP' }, publicKey, raw))
}

/**
 * Dechiffre une DEK avec sa propre cle privee RSA.
 * @param {string} wrappedB64
 * @param {CryptoKey} privateKey
 * @returns {Promise<CryptoKey>} DEK NON extractible.
 */
export async function unwrapDek(wrappedB64, privateKey) {
    const raw = await crypto.subtle.decrypt(
        { name: 'RSA-OAEP' },
        privateKey,
        b64ToBuf(wrappedB64),
    )
    return crypto.subtle.importKey('raw', raw, { name: 'AES-GCM' }, false, [
        'encrypt',
        'decrypt',
    ])
}