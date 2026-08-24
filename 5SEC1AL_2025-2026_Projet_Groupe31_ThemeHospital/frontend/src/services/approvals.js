/**
 * @file Approbation et refus des depots faits par un medecin.
 *
 * REGLE DU PROJET : un medecin PROPOSE, seul le patient DISPOSE.
 *
 * Tant que le patient n'a pas signe un manifeste neuf, le fichier depose
 * par le medecin n'existe pas aux yeux du dossier. Le serveur le stocke,
 * mais la liste qui fait foi ne le mentionne pas.
 */

import { importPublicKey, signBytes } from '@/crypto/keys.js'
import { rewrapDek } from '@/crypto/files.js'
import { apiGet, apiPost, apiDelete } from './api.js'
import { fetchRecord } from './records.js'
import { listLinks } from './doctors.js'

const enc = new TextEncoder()

/**
 * Construit et signe le manifeste resultant d'une modification du dossier.
 *
 * @param {string} patientSub
 * @param {(anciens: string[]) => string[]} transformer Nouvelle liste.
 * @param {CryptoKey} signingKey
 * @returns {Promise<{manifest_content: string, manifest_signature: string,
 *                    manifest_version: number}>}
 */
async function signerNouveauManifeste(patientSub, transformer, signingKey) {
    const record = await fetchRecord(patientSub)
    const anciens = record.manifest ? JSON.parse(record.manifest.content).files : []
    const version = (record.manifest ? record.manifest.version : 0) + 1

    const manifest_content = JSON.stringify({ version, files: transformer(anciens) })

    return {
        manifest_content,
        manifest_signature: await signBytes(enc.encode(manifest_content), signingKey),
        manifest_version: version,
    }
}

/**
 * Le patient approuve un fichier depose par un medecin.
 *
 * Trois choses se produisent ensemble, dans une seule transaction serveur :
 *   - le fichier passe en `approved` ;
 *   - il rejoint le manifeste signe (et si c'est une EDITION, l'ancien en
 *     sort et est supprime) ;
 *   - sa DEK est rechiffree pour les AUTRES medecins approuves, afin que
 *     le dossier reste coherent pour tout le monde.
 *
 * @param {object} fichier Element de record.files.
 * @param {{patientSub: string, signingKey: CryptoKey, privateKey: CryptoKey}} cles
 * @returns {Promise<object>}
 */
export async function approveFile(fichier, cles) {
    const manifeste = await signerNouveauManifeste(
        cles.patientSub,
        // Une edition remplace : on retire l'ancien, on ajoute le nouveau.
        (anciens) => anciens.filter((id) => id !== fichier.replaces).concat(fichier.id),
        cles.signingKey,
    )

    // La DEK de CE fichier, telle que le medecin l'a scellee pour le patient.
    const stored = await apiGet(`/records/files/${fichier.id}`)

    const wrapped_keys = []
    for (const lien of await listLinks()) {
        if (lien.status !== 'approved') continue
        if (!lien.doctor_public_key) continue
        // L'auteur du depot possede deja sa cle : il l'a fabriquee lui-meme.
        if (lien.doctor_id === fichier.uploaded_by) continue

        wrapped_keys.push({
            recipient_sub: lien.doctor_id,
            wrapped_dek: await rewrapDek(
                stored.wrapped_dek,
                cles.privateKey,
                await importPublicKey(lien.doctor_public_key),
            ),
        })
    }

    return apiPost(`/records/files/${fichier.id}/approve`, { ...manifeste, wrapped_keys })
}

/**
 * Le patient refuse un depot.
 *
 * Aucun manifeste n'est requis : le fichier n'y a JAMAIS figure. Il n'a
 * donc jamais fait partie du dossier, et le refuser ne change rien a la
 * liste signee.
 *
 * @param {string} fileId
 * @returns {Promise<object>}
 */
export function rejectFile(fileId) {
    return apiPost(`/records/files/${fileId}/reject`, {})
}


/**
 * Un medecin DEMANDE la suppression d'un fichier. Il ne supprime rien.
 *
 * Le fichier reste dans le dossier ET dans le manifeste : seul son statut
 * change, pour signaler la demande au patient.
 *
 * @param {string} fileId
 * @returns {Promise<object>}
 */
export function requestDeletion(fileId) {
    return apiPost(`/records/files/${fileId}/request-deletion`, {})
}

/**
 * Le patient REFUSE une demande de suppression : le fichier redevient
 * `approved`. Le dernier mot appartient au proprietaire du dossier.
 *
 * @param {string} fileId
 * @returns {Promise<object>}
 */
export function keepFile(fileId) {
    return apiPost(`/records/files/${fileId}/keep`, {})
}

/**
 * Le patient supprime un fichier de son dossier.
 *
 * UN SEUL point de sortie, que la demande vienne d'un medecin ou du
 * patient lui-meme. La suppression s'accompagne OBLIGATOIREMENT d'un
 * manifeste neuf : sans lui, la liste signee mentionnerait encore un
 * fichier disparu, et la lecture suivante crierait a la falsification.
 *
 * @param {string} fileId
 * @param {{patientSub: string, signingKey: CryptoKey}} cles
 * @returns {Promise<object>}
 */
export async function deleteFile(fileId, cles) {
    const manifeste = await signerNouveauManifeste(
        cles.patientSub,
        (anciens) => anciens.filter((id) => id !== fileId),
        cles.signingKey,
    )
    return apiDelete(`/records/files/${fileId}/delete`, manifeste)
}