/**
 * @file Depot, lecture et VERIFICATION du dossier medical.
 *
 * Toute la cryptographie a lieu ici, dans le navigateur. Le serveur ne
 * recoit que des blocs chiffres et un manifeste signe qu'il ne peut ni
 * lire ni forger.
 */

import { importPublicKey, signBytes, verifyBytes, SIGN_ALG } from '@/crypto/keys.js'
import {
    generateDek,
    encryptDocument,
    decryptDocument,
    wrapDek,
    unwrapDek,
} from '@/crypto/files.js'
import { apiGet, apiPost } from './api.js'

const enc = new TextEncoder()

/**
 * Recupere les metadonnees des fichiers ET le manifeste signe.
 * @param {string} patientSub
 * @returns {Promise<{files: object[], manifest: object|null}>}
 */
export async function fetchRecord(patientSub) {
    return apiGet(`/records/record/${patientSub}`)
}

/**
 * VERIFIE que la liste livree par le serveur correspond a la liste signee.
 *
 * C'est la reponse a la question 4 de la check-list. Le chiffrement protege
 * chaque fichier ; cette verification protege la LISTE.
 *
 * @param {{files: object[], manifest: object|null}} record
 * @param {string} signingPublicKeyB64 Cle publique de signature du patient.
 * @returns {Promise<{ok: boolean, raison?: string}>}
 */
export async function verifyRecord(record, signingPublicKeyB64) {
    const approuves = record.files.filter((f) => f.status === 'approved')

    if (!record.manifest) {
        return approuves.length === 0
            ? { ok: true, raison: 'Dossier vide, aucun manifeste attendu.' }
            : { ok: false, raison: 'Des fichiers existent SANS manifeste signe.' }
    }

    const cle = await importPublicKey(signingPublicKeyB64, SIGN_ALG, ['verify'])

    // verifyBytes renvoie false, elle ne leve PAS d'exception : il faut
    // imperativement tester la valeur de retour.
    const signatureValide = await verifyBytes(
        enc.encode(record.manifest.content),
        record.manifest.signature,
        cle,
    )
    if (!signatureValide) {
        return { ok: false, raison: 'Signature du manifeste INVALIDE.' }
    }

    const signes = new Set(JSON.parse(record.manifest.content).files)
    const livres = new Set(approuves.map((f) => f.id))

    // Comparaison dans les DEUX sens : detecte une suppression comme un ajout.
    for (const id of signes) {
        if (!livres.has(id)) {
            return { ok: false, raison: `Fichier SUPPRIME par le serveur : ${id}` }
        }
    }
    for (const id of livres) {
        if (!signes.has(id)) {
            return { ok: false, raison: `Fichier AJOUTE hors manifeste : ${id}` }
        }
    }

    return { ok: true, raison: `${signes.size} fichier(s) verifie(s).` }
}

/**
 * Chiffre un fichier et le depose, en mettant a jour le manifeste signe.
 *
 * L'UUID est genere par le CLIENT : il doit figurer dans le manifeste
 * signe avant l'envoi. Le serveur en verifie l'unicite.
 *
 * @param {{file: File, examDate: string}} document
 * @param {{patientSub: string, publicKey: string, signingKey: CryptoKey}} cles
 * @returns {Promise<{fileId: string, version: number}>}
 */
export async function uploadFile({ file, examDate }, cles) {
    const record = await fetchRecord(cles.patientSub)
    const fileId = crypto.randomUUID()

    // 1. Une cle de donnees propre a CE fichier.
    const dek = await generateDek()

    // 2. Nom, date et contenu chiffres ensemble, en un seul bloc.
    const blob = await encryptDocument(
        { filename: file.name, examDate, content: await file.arrayBuffer() },
        dek,
    )

    // 3. La DEK chiffree pour le patient. En Phase 7, une par medecin approuve.
    const publique = await importPublicKey(cles.publicKey)
    const dekChiffree = await wrapDek(dek, publique)

    // 4. Nouveau manifeste, signe AVANT l'envoi.
    const anciens = record.manifest ? JSON.parse(record.manifest.content).files : []
    const version = (record.manifest ? record.manifest.version : 0) + 1
    const manifestContent = JSON.stringify({ version, files: [...anciens, fileId] })
    const signature = await signBytes(enc.encode(manifestContent), cles.signingKey)

    // 5. Envoi atomique : fichier, cle et manifeste dans la meme transaction.
    await apiPost('/records/files', {
        file_id: fileId,
        patient_sub: cles.patientSub,
        ciphertext: blob.ciphertext,
        iv: blob.iv,
        wrapped_keys: [{ recipient_sub: cles.patientSub, wrapped_dek: dekChiffree }],
        manifest_content: manifestContent,
        manifest_signature: signature,
        manifest_version: version,
    })

    return { fileId, version }
}

/**
 * Recupere un fichier et le dechiffre.
 * @param {string} fileId
 * @param {CryptoKey} privateKey Cle privee de chiffrement de l'appelant.
 * @returns {Promise<{filename: string, examDate: string, content: ArrayBuffer}>}
 */
export async function downloadFile(fileId, privateKey) {
    const stored = await apiGet(`/records/files/${fileId}`)
    const dek = await unwrapDek(stored.wrapped_dek, privateKey)
    return decryptDocument({ iv: stored.iv, ciphertext: stored.ciphertext }, dek)
}


/**
 * Depot d'un fichier par un MEDECIN dans le dossier d'un patient.
 *
 * Deux differences essentielles avec le depot par le patient :
 *
 *   1. AUCUN MANIFESTE n'est envoye. Le medecin ne possede pas la cle de
 *      signature du patient, il ne PEUT donc pas modifier la liste signee.
 *      Le fichier arrive en `pending_approval`, hors du dossier officiel.
 *
 *   2. La DEK est scellee POUR DEUX personnes : le medecin (pour se
 *      relire) et le patient (pour pouvoir OUVRIR le fichier avant de
 *      l'approuver). Approuver a l'aveugle n'aurait aucun sens.
 *
 * @param {{file: File, examDate: string}} document
 * @param {{patientSub: string, patientPublicKey: string, doctorSub: string,
 *          doctorPublicKey: string, replaces?: string}} contexte
 * @returns {Promise<{fileId: string}>}
 */
export async function uploadFileAsDoctor({ file, examDate }, contexte) {
    if (!contexte.patientPublicKey) {
        throw new Error("Ce patient n'a pas enregistre ses cles.")
    }

    const fileId = crypto.randomUUID()
    const dek = await generateDek()

    const blob = await encryptDocument(
        { filename: file.name, examDate, content: await file.arrayBuffer() },
        dek,
    )

    const clePatient = await importPublicKey(contexte.patientPublicKey)
    const cleMedecin = await importPublicKey(contexte.doctorPublicKey)

    await apiPost('/records/files', {
        file_id: fileId,
        patient_sub: contexte.patientSub,
        ciphertext: blob.ciphertext,
        iv: blob.iv,
        wrapped_keys: [
            { recipient_sub: contexte.patientSub, wrapped_dek: await wrapDek(dek, clePatient) },
            { recipient_sub: contexte.doctorSub, wrapped_dek: await wrapDek(dek, cleMedecin) },
        ],
        replaces: contexte.replaces || null,
    })

    return { fileId }
}