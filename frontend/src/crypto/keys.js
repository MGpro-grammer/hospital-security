/**
 * @file Derivation de cle et gestion des cles cryptographiques du patient.
 *
 * Chaine complete :
 *   WebAuthn PRF -> HKDF -> KEK (AES-256-GCM) -> chiffre la cle privee RSA.
 *
 * Aucun secret ne quitte le navigateur en clair. Le serveur ne recoit que
 * la cle publique (en clair, c'est son role) et la cle privee chiffree,
 * qu'il est incapable de dechiffrer.
 */

/** Sel passe a l'authentificateur. Fixe : il identifie l'usage, pas l'utilisateur. */
const PRF_SALT = new TextEncoder().encode('hospital-security/kek/v1')

/** Parametres HKDF. `info` assure la separation de domaine entre usages. */
const HKDF_SALT = new TextEncoder().encode('hospital-security/hkdf/v1')
const HKDF_INFO = new TextEncoder().encode('kek-aes256-gcm-v1')

/**
 * Encode un buffer binaire en base64 (transport JSON vers Django).
 * @param {ArrayBuffer|Uint8Array} buf
 * @returns {string}
 */
export function bufToB64(buf) {
    const bytes = new Uint8Array(buf)
    let bin = ''
    for (const b of bytes) bin += String.fromCharCode(b)
    return btoa(bin)
}

/**
 * Decode une chaine base64 en buffer binaire.
 * @param {string} b64
 * @returns {ArrayBuffer}
 */
export function b64ToBuf(b64) {
    const bin = atob(b64)
    const bytes = new Uint8Array(bin.length)
    for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
    return bytes.buffer
}

/**
 * Demande a l'authentificateur d'evaluer le PRF sur la cle de l'utilisateur.
 * Declenche une verification Windows Hello (PIN ou biometrie).
 *
 * @param {string} [rpId] Identifiant du site relais. Defaut : l'hote courant.
 * @returns {Promise<Uint8Array>} 32 octets, deterministes pour un meme couple
 *          (cle, sel). Jamais stockes : recalcules a chaque session.
 * @throws {Error} Si l'authentificateur ne fournit pas de resultat PRF.
 */
export async function evaluatePrf(rpId = location.hostname) {
    const assertion = await navigator.credentials.get({
        publicKey: {
            challenge: crypto.getRandomValues(new Uint8Array(32)),
            rpId,
            userVerification: 'required',
            extensions: { prf: { eval: { first: PRF_SALT } } },
        },
    })

    // On teste le RESULTAT, jamais prf.enabled : ce dernier vaut false sur
    // Windows Hello alors que PRF fonctionne (verifie en Phase 2 et 4).
    const out = assertion.getClientExtensionResults()?.prf?.results?.first
    if (!out) throw new Error('PRF indisponible sur cet authentificateur.')
    return new Uint8Array(out)
}

/**
 * Transforme la sortie brute du PRF en cle AES-256 exploitable.
 *
 * HKDF n'ajoute pas d'entropie : la sortie PRF en a deja. Il assure la mise
 * en forme du secret et la separation de domaine via `info`, ce qui permettra
 * de deriver d'autres cles independantes du meme secret si besoin.
 *
 * @param {Uint8Array} prfOutput
 * @returns {Promise<CryptoKey>} KEK NON extractible : elle ne peut jamais
 *          etre lue par le code JavaScript, meme compromis.
 */
export async function deriveKek(prfOutput) {
    const base = await crypto.subtle.importKey('raw', prfOutput, 'HKDF', false, ['deriveKey'])
    return crypto.subtle.deriveKey(
        { name: 'HKDF', hash: 'SHA-256', salt: HKDF_SALT, info: HKDF_INFO },
        base,
        { name: 'AES-GCM', length: 256 },
        false,
        ['encrypt', 'decrypt'],
    )
}

/**
 * Genere la paire RSA-OAEP 2048 de l'utilisateur, dans le navigateur.
 * @returns {Promise<CryptoKeyPair>}
 */
export async function generateKeyPair() {
    return crypto.subtle.generateKey(
        {
            name: 'RSA-OAEP',
            modulusLength: 2048,
            publicExponent: new Uint8Array([1, 0, 1]), // 65537
            hash: 'SHA-256',
        },
        true, // extractible : necessaire pour exporter puis chiffrer la cle privee
        ['encrypt', 'decrypt'],
    )
}

/**
 * Chiffre la cle privee avec la KEK, avant tout envoi reseau.
 * @param {CryptoKey} privateKey
 * @param {CryptoKey} kek
 * @returns {Promise<{iv: string, ciphertext: string}>} base64
 */
export async function wrapPrivateKey(privateKey, kek) {
    const pkcs8 = await crypto.subtle.exportKey('pkcs8', privateKey)
    const iv = crypto.getRandomValues(new Uint8Array(12))
    const ct = await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, kek, pkcs8)
    return { iv: bufToB64(iv), ciphertext: bufToB64(ct) }
}

/**
 * Dechiffre la cle privee recuperee du serveur.
 * AES-GCM verifie l'integrite : toute alteration fait echouer l'operation.
 *
 * @param {{iv: string, ciphertext: string}} wrapped
 * @param {CryptoKey} kek
 * @returns {Promise<CryptoKey>} Cle privee NON extractible.
 */
export async function unwrapPrivateKey(wrapped, kek) {
    const pkcs8 = await crypto.subtle.decrypt(
        { name: 'AES-GCM', iv: b64ToBuf(wrapped.iv) },
        kek,
        b64ToBuf(wrapped.ciphertext),
    )
    return crypto.subtle.importKey('pkcs8', pkcs8, { name: 'RSA-OAEP', hash: 'SHA-256' }, false, [
        'decrypt',
    ])
}

/**
 * Exporte la cle publique au format SPKI base64.
 * @param {CryptoKey} publicKey
 * @returns {Promise<string>}
 */
export async function exportPublicKey(publicKey) {
    return bufToB64(await crypto.subtle.exportKey('spki', publicKey))
}

/**
 * Importe une cle publique SPKI base64 (la sienne, ou celle d'un medecin).
 * @param {string} b64
 * @returns {Promise<CryptoKey>}
 */
export async function importPublicKey(b64) {
    return crypto.subtle.importKey('spki', b64ToBuf(b64), { name: 'RSA-OAEP', hash: 'SHA-256' }, false, [
        'encrypt',
    ])
}