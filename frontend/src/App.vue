<script>
import { login, logout, handleRedirect } from '@/services/auth.js'
import { enroll, restoreKeys } from '@/services/enrollment.js'
import { apiGet, apiPost } from '@/services/api.js'
import {
  fetchRecord,
  verifyRecord,
  uploadFile,
  downloadFile,
} from '@/services/records.js'

import {
  listDoctors,
  listPatients,
  listLinks,
  addDoctor,
  approveDoctor,
  removeDoctor,
  requestAccess,
} from '@/services/doctors.js'

export default {
  name: 'App',

  data() {
    return {
      journal: '',
      utilisateur: null,
      patientSub: null,
      cles: null,
      prenom: 'Jean',
      nom: 'Dupont',
      naissance: '1990-05-14',
      organisation: 'Hopital Saint-Luc',
      fichierChoisi: null,
      dateExamen: '2026-03-12',
      fichiers: [],
      estPatient: false,
      estMedecin: false,
      rechercheMedecin: '',
      medecins: [],
      liens: [],
      recherchePatient: '',
      patients: [],
    }
  },

  async mounted() {
    try {
      const claims = await handleRedirect()
      if (claims) {
        this.utilisateur = claims.preferred_username
        this.patientSub = claims.sub
        this.log(`Connecte : ${claims.preferred_username}`)
        const groupes = claims.groups || []
        this.estPatient = groupes.includes('patients')
        this.estMedecin = groupes.includes('doctors')
        this.log(`Groupes  : ${groupes.join(', ') || 'aucun'}`)
        this.log('')
      }
    } catch (e) {
      this.log(`ERREUR connexion : ${e.message}`)
    }
  },

  methods: {
    /** @param {string} m */
    log(m) {
      this.journal += m + '\n'
    },

    /** @param {Error} e */
    erreur(e) {
      this.log(`ERREUR : ${e.message}`)
      this.log('')
    },

    seConnecter() {
      login()
    },

    seDeconnecter() {
      logout()
    },

    async creerProfil() {
      try {
        // On envoie les champs des DEUX roles. Django n'exploite que ceux
        // du serialiseur correspondant au groupe porte par le jeton, et
        // ignore silencieusement les autres. Le client ne choisit donc
        // toujours PAS son role : c'est le jeton qui le decide.
        await apiPost('/profile', {
          first_name: this.prenom,
          last_name: this.nom,
          date_of_birth: this.naissance,
          organisation: this.organisation,
        })
        this.log('Profil cree.')
        this.log('')
      } catch (e) {
        this.erreur(e)
      }
    },

    async voirProfil() {
      try {
        const p = await apiGet('/profile/me')
        this.log(`Profil : ${p.role} - ${p.first_name} ${p.last_name}`)
        this.log('')
      } catch (e) {
        this.erreur(e)
      }
    },

    async enregistrerCles() {
      try {
        this.log('Generation des deux paires de cles...')
        await enroll()
        this.log('Cles enregistrees sur le serveur.')
        this.log('')
      } catch (e) {
        this.erreur(e)
      }
    },

    async deverrouiller() {
      try {
        this.log('Dechiffrement des cles privees...')
        this.cles = await restoreKeys()
        this.log('Cles deverrouillees pour cette session.')
        this.log('')
      } catch (e) {
        this.erreur(e)
      }
    },

    /** @param {Event} evt */
    choisirFichier(evt) {
      this.fichierChoisi = evt.target.files[0] || null
    },

    async deposer() {
      if (!this.cles) return this.log('Deverrouillez vos cles d abord.\n')
      if (!this.fichierChoisi) return this.log('Choisissez un fichier.\n')
      try {
        this.log(`Chiffrement de "${this.fichierChoisi.name}"...`)
        const r = await uploadFile(
            { file: this.fichierChoisi, examDate: this.dateExamen },
            {
              patientSub: this.patientSub,
              publicKey: this.cles.publicKey,
              signingKey: this.cles.signingKey,
            },
        )
        this.log(`Depose. Identifiant ${r.fileId}, manifeste v${r.version}.`)
        this.log('')
      } catch (e) {
        this.erreur(e)
      }
    },

    async lireDossier() {
      if (!this.cles) return this.log('Deverrouillez vos cles d abord.\n')
      try {
        const record = await fetchRecord(this.patientSub)
        this.fichiers = record.files
        this.log(`=== DOSSIER : ${record.files.length} fichier(s) ===`)

        const v = await verifyRecord(record, this.cles.signingPublicKey)
        this.log(v.ok ? `MANIFESTE VALIDE - ${v.raison}` : `ALERTE : ${v.raison}`)
        this.log('')
      } catch (e) {
        this.erreur(e)
      }
    },

    async chargerMedecins() {
      try {
        this.medecins = await listDoctors(this.rechercheMedecin)
        this.log(`${this.medecins.length} medecin(s) trouve(s).`)
        this.log('')
      } catch (e) {
        this.erreur(e)
      }
    },

    async chargerLiens() {
      try {
        this.liens = await listLinks()
        this.log(`=== AUTORISATIONS : ${this.liens.length} ===`)
        for (const l of this.liens) {
          const qui = this.estMedecin ? l.patient_name : l.doctor_name
          this.log(`#${l.id} ${qui} - ${l.status} (demande par ${l.initiated_by})`)
        }
        this.log('')
      } catch (e) {
        this.erreur(e)
      }
    },

    /** @param {object} medecin */
    async autoriser(medecin) {
      if (!this.cles) return this.log('Deverrouillez vos cles d abord.\n')
      try {
        this.log(`Rechiffrement des cles pour ${medecin.last_name}...`)
        const r = await addDoctor(medecin, {
          patientSub: this.patientSub,
          privateKey: this.cles.privateKey,
        })
        this.log(`Medecin autorise. ${r.cles_partagees} cle(s) partagee(s).`)
        this.log('')
        await this.chargerLiens()
      } catch (e) {
        this.erreur(e)
      }
    },

    /** @param {object} lien */
    async approuver(lien) {
      if (!this.cles) return this.log('Deverrouillez vos cles d abord.\n')
      try {
        this.log(`Approbation de ${lien.doctor_name}...`)
        const r = await approveDoctor(lien, {
          patientSub: this.patientSub,
          privateKey: this.cles.privateKey,
        })
        this.log(`Demande approuvee. ${r.cles_partagees} cle(s) partagee(s).`)
        this.log('')
        await this.chargerLiens()
      } catch (e) {
        this.erreur(e)
      }
    },

    /** @param {object} lien */
    async retirer(lien) {
      try {
        const r = await removeDoctor(lien.id)
        this.log(`${r.detail} ${r.cles_supprimees} cle(s) supprimee(s).`)
        this.log('')
        await this.chargerLiens()
      } catch (e) {
        this.erreur(e)
      }
    },

    async chercherPatients() {
      try {
        this.patients = await listPatients(this.recherchePatient)
        this.log(`${this.patients.length} patient(s) trouve(s).`)
        this.log('')
      } catch (e) {
        this.erreur(e)
      }
    },

    /** @param {object} p */
    async demanderAcces(p) {
      try {
        await requestAccess(p.keycloak_sub)
        this.log(`Demande envoyee a ${p.first_name} ${p.last_name}.`)
        this.log('En attente de l approbation du patient.')
        this.log('')
        await this.chargerLiens()
      } catch (e) {
        this.erreur(e)
      }
    },

    /** @param {object} lien */
    async lireDossierDe(lien) {
      if (!this.cles) return this.log('Deverrouillez vos cles d abord.\n')
      try {
        const record = await fetchRecord(lien.patient_id)
        this.fichiers = record.files
        this.log(`=== DOSSIER DE ${lien.patient_name} : ${record.files.length} fichier(s) ===`)

        // Le medecin verifie le manifeste avec la cle de signature du
        // PATIENT : il s'assure que le serveur ne lui cache ni ne lui
        // ajoute aucun fichier. Il ne fait pas plus confiance au serveur
        // que le patient lui-meme.
        if (!lien.patient_signing_public_key) {
          this.log('ALERTE : ce patient n a pas de cle de signature.')
        } else {
          const v = await verifyRecord(record, lien.patient_signing_public_key)
          this.log(v.ok ? `MANIFESTE VALIDE - ${v.raison}` : `ALERTE : ${v.raison}`)
        }
        this.log('')
      } catch (e) {
        this.erreur(e)
      }
    },

    /** @param {string} id */
    async ouvrir(id) {
      try {
        const doc = await downloadFile(id, this.cles.privateKey)
        this.log(`=== ${id} ===`)
        this.log(`Nom   : ${doc.filename}`)
        this.log(`Date  : ${doc.examDate}`)
        this.log(`Poids : ${doc.content.byteLength} octets`)
        this.log(`Debut : ${new TextDecoder().decode(doc.content.slice(0, 60))}`)
        this.log('')
      } catch (e) {
        this.erreur(e)
      }
    },
  },
}
</script>

<template>
  <main>
    <h1>Hospital Security</h1>
    <p v-if="utilisateur">Utilisateur : <strong>{{ utilisateur }}</strong></p>
    <p v-else>Non connecte.</p>

    <section>
      <button @click="seConnecter" :disabled="!!utilisateur">1. Se connecter</button>
      <button @click="seDeconnecter" v-if="utilisateur">Se deconnecter</button>
    </section>

    <section v-if="utilisateur">
      <h2>Profil</h2>
      <input v-model="prenom" placeholder="Prenom" />
      <input v-model="nom" placeholder="Nom" />
      <input v-model="naissance" type="date" />
      <input v-if="estMedecin" v-model="organisation" placeholder="Organisation" />
      <button @click="creerProfil">2. Creer mon profil</button>
      <button @click="voirProfil">Voir mon profil</button>
    </section>

    <section v-if="utilisateur">
      <h2>Cles</h2>
      <button @click="enregistrerCles">3. Enregistrer mes cles</button>
      <button @click="deverrouiller">4. Deverrouiller mes cles</button>
    </section>

    <section v-if="cles && estPatient">
      <h2>Dossier medical</h2>
      <input type="file" @change="choisirFichier" />
      <input v-model="dateExamen" type="date" />
      <button @click="deposer">5. Deposer le fichier</button>
      <button @click="lireDossier">6. Lire mon dossier</button>

      <ul v-if="fichiers.length">
        <li v-for="f in fichiers" :key="f.id">
          {{ f.id }} — {{ f.status }}
          <button @click="ouvrir(f.id)">Ouvrir</button>
        </li>
      </ul>
    </section>

    <section v-if="cles && estPatient">
      <h2>Mes medecins</h2>

      <input v-model="rechercheMedecin" placeholder="Nom du medecin" />
      <button @click="chargerMedecins">7. Chercher un medecin</button>

      <ul v-if="medecins.length">
        <li v-for="m in medecins" :key="m.keycloak_sub">
          Dr {{ m.first_name }} {{ m.last_name }} ({{ m.organisation }})
          <button @click="autoriser(m)" :disabled="!m.public_key">Autoriser</button>
          <em v-if="!m.public_key">cles non enregistrees</em>
        </li>
      </ul>

      <p><button @click="chargerLiens">8. Voir mes autorisations</button></p>

      <ul v-if="liens.length">
        <li v-for="l in liens" :key="l.id">
          {{ l.doctor_name }} — <strong>{{ l.status }}</strong>
          <button v-if="l.status === 'pending'" @click="approuver(l)">Approuver</button>
          <button @click="retirer(l)">Retirer</button>
        </li>
      </ul>
    </section>

    <section v-if="cles && estMedecin">
      <h2>Mes patients</h2>

      <input v-model="recherchePatient" placeholder="Nom du patient" />
      <button @click="chercherPatients">7. Chercher un patient</button>

      <ul v-if="patients.length">
        <li v-for="p in patients" :key="p.keycloak_sub">
          {{ p.first_name }} {{ p.last_name }}
          <button @click="demanderAcces(p)">Demander l acces</button>
        </li>
      </ul>

      <p><button @click="chargerLiens">8. Voir mes acces</button></p>

      <ul v-if="liens.length">
        <li v-for="l in liens" :key="l.id">
          {{ l.patient_name }} — <strong>{{ l.status }}</strong>
          <button v-if="l.status === 'approved'" @click="lireDossierDe(l)">
            Ouvrir le dossier
          </button>
        </li>
      </ul>

      <ul v-if="fichiers.length">
        <li v-for="f in fichiers" :key="f.id">
          {{ f.id }} — {{ f.status }}
          <button @click="ouvrir(f.id)">Ouvrir</button>
        </li>
      </ul>
    </section>

    <pre>{{ journal }}</pre>
  </main>
</template>

<style scoped>
main { font-family: system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; }
section { margin: 1.2rem 0; }
h2 { font-size: 1rem; margin-bottom: .4rem; }
button, input { padding: .5rem .8rem; margin: .2rem .2rem .2rem 0; font-size: .95rem; }
button { cursor: pointer; }
li { margin: .3rem 0; font-family: monospace; font-size: .85rem; }
pre { background: #f4f4f4; padding: 1rem; white-space: pre-wrap; word-break: break-all; }
</style>