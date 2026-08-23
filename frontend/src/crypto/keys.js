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
 * Dechiffre une cle privee recuperee du serveur.
 * AES-GCM verifie l'integrite : toute alteration fait echouer l'operation.
 *
 * @param {{iv: string, ciphertext: string}} wrapped
 * @param {CryptoKey} kek
 * @param {object} [algorithm] Algorithme de la cle a reconstruire.
 * @param {string[]} [usages] Usages autorises.
 * @returns {Promise<CryptoKey>} Cle privee NON extractible.
 */
export async function unwrapPrivateKey(
    wrapped,
    kek,
    algorithm = { name: 'RSA-OAEP', hash: 'SHA-256' },
    usages = ['decrypt'],
) {
    const pkcs8 = await crypto.subtle.decrypt(
        { name: 'AES-GCM', iv: b64ToBuf(wrapped.iv) },
        kek,
        b64ToBuf(wrapped.ciphertext),
    )
    return crypto.subtle.importKey('pkcs8', pkcs8, algorithm, false, usages)
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
 * Importe une cle publique SPKI base64.
 * @param {string} b64
 * @param {object} [algorithm]
 * @param {string[]} [usages]
 * @returns {Promise<CryptoKey>}
 */
export async function importPublicKey(
    b64,
    algorithm = { name: 'RSA-OAEP', hash: 'SHA-256' },
    usages = ['encrypt'],
) {
    return crypto.subtle.importKey('spki', b64ToBuf(b64), algorithm, false, usages)
}

// --- Signature du manifeste ------------------------------------------

/** Algorithme de la paire de signature. Distinct de la paire de chiffrement. */
export const SIGN_ALG = { name: 'RSA-PSS', hash: 'SHA-256' }

/** Longueur du sel PSS, alignee sur la taille d'une empreinte SHA-256. */
const PSS_SALT_LENGTH = 32

/**
 * Genere la paire de SIGNATURE de l'utilisateur.
 *
 * Une paire distincte de la paire de chiffrement : Web Crypto fixe
 * l'algorithme a la creation, et RSA-OAEP ne sait pas signer. Separer la
 * cle qui chiffre de celle qui signe est par ailleurs une bonne pratique.
 *
 * @returns {Promise<CryptoKeyPair>}
 */
export async function generateSigningKeyPair() {
    return crypto.subtle.generateKey(
        {
            name: 'RSA-PSS',
            modulusLength: 2048,
            publicExponent: new Uint8Array([1, 0, 1]),
            hash: 'SHA-256',
        },
        true,
        ['sign', 'verify'],
    )
}

/**
 * Signe des octets avec la cle privee de signature.
 * @param {Uint8Array} data
 * @param {CryptoKey} privateKey
 * @returns {Promise<string>} Signature base64.
 */
export async function signBytes(data, privateKey) {
    const sig = await crypto.subtle.sign(
        { name: 'RSA-PSS', saltLength: PSS_SALT_LENGTH },
        privateKey,
        data,
    )
    return bufToB64(sig)
}

/**
 * Verifie une signature.
 * @param {Uint8Array} data
 * @param {string} signatureB64
 * @param {CryptoKey} publicKey
 * @returns {Promise<boolean>} false si la signature ne correspond pas.
 */
export async function verifyBytes(data, signatureB64, publicKey) {
    return crypto.subtle.verify(
        { name: 'RSA-PSS', saltLength: PSS_SALT_LENGTH },
        publicKey,
        b64ToBuf(signatureB64),
        data,
    )
}