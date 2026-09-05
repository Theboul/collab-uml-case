import { Injectable } from '@angular/core';
import { SignalingService } from './signaling.service';

type Peer = {
  pc: RTCPeerConnection;
  dc?: RTCDataChannel;
};

@Injectable({ providedIn: 'root' })
export class P2PService {
  private peers = new Map<string, Peer>();
  private localId = ''; // mi channel_name (lo asigna el servidor en presence)
  public onData?: (from: string, data: any) => void;

  constructor(private signaling: SignalingService) {}

  init(roomId: string) {
    this.signaling.onMessage = (msg) => this.handleSignaling(msg);
    this.signaling.connect(roomId);
  }

  private iceServers: RTCIceServer[] = [
    { urls: ['stun:stun.l.google.com:19302'] },
    // TURN opcional si sales a internet:
    // { urls: ['turn:yourturn.com:3478'], username: 'user', credential: 'pass' }
  ];

  private newPeer(remoteId: string, isInitiator: boolean) {
    //console.log(`[P2P] Creando peer con ${remoteId}, initiator=${isInitiator}`);
    const pc = new RTCPeerConnection({ iceServers: this.iceServers });
    const peer: Peer = { pc };
    this.peers.set(remoteId, peer);

    pc.onicecandidate = (e) => {
      if (e.candidate) {
        this.signaling.sendSignal(remoteId, { type: 'ice', candidate: e.candidate });
      }
    };

    if (isInitiator) {
      const dc = pc.createDataChannel('canvas');
      this.attachDataChannel(remoteId, dc);
      pc.createOffer().then(offer => {
        pc.setLocalDescription(offer);
        this.signaling.sendSignal(remoteId, { type: 'offer', sdp: offer });
        //console.log(`[P2P] Offer enviada a ${remoteId}`);
      });
    } else {
      pc.ondatachannel = (ev) => this.attachDataChannel(remoteId, ev.channel);
    }

    return peer;
  }

  private attachDataChannel(remoteId: string, dc: RTCDataChannel) {
    const p = this.peers.get(remoteId);
    if (!p) {
      console.error(`[P2P] Peer no encontrado para ${remoteId}`);
      return;
    }
    p.dc = dc;
    dc.onopen = () => {
      if (this.onData) {
        this.onData(remoteId, { t: 'request_full_state' } as any);
        
      }
    };
    dc.onmessage = (ev) => {
      try {
        this.onData && this.onData(remoteId, JSON.parse(ev.data));
      } catch (e) {
        console.error('[P2P] Error parsing mensaje remoto:', e);
      }
    };
  }


  private async handleSignaling(msg: any) {

    if (msg.type === 'presence') {
      if (msg.peer && !this.localId) {
        this.localId = msg.peer;
        //console.log('[P2P] Mi localId:', this.localId);
      }
      if (msg.action === 'join') {
        //console.log(`[P2P] PRESENCE join de ${msg.peer}`);
        // Aviso a la sala que estoy disponible
        this.signaling.broadcast({ type: 'announce' });
      }
      return;
    }

    if (msg.type === 'broadcast' && msg.payload?.type === 'announce') {
      const remoteId = msg.from;
      if (this.peers.has(remoteId)) return;

      // regla: el que tiene ID menor inicia
      const isInitiator = this.localId < remoteId;
      this.newPeer(remoteId, isInitiator);
      return;
    }

    if (msg.type === 'signal') {
      const remoteId = msg.from;
      let peer = this.peers.get(remoteId);
      if (!peer) peer = this.newPeer(remoteId, false);
      const pc = peer.pc;
      const payload = msg.payload;

      if (payload.type === 'offer') {
        //console.log(`[P2P] Offer recibido de ${remoteId}`);
        await pc.setRemoteDescription(new RTCSessionDescription(payload.sdp));
        const answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);
        this.signaling.sendSignal(remoteId, { type: 'answer', sdp: answer });
        //console.log(`[P2P] Answer enviada a ${remoteId}`);
      } else if (payload.type === 'answer') {
        if (pc.signalingState !== 'stable') {
          await pc.setRemoteDescription(new RTCSessionDescription(payload.sdp));
        }
      } else if (payload.type === 'ice' && payload.candidate) {
        try {
          await pc.addIceCandidate(payload.candidate);
          //console.log(`[P2P] ICE aplicado de ${remoteId}`);
        } catch (e) {
          console.warn('[P2P] Error aplicando ICE:', e);
        }
      }
    }
  }

  sendToAll(data: any) {
  const json = JSON.stringify(data);
  for (const [id, p] of this.peers) {
    if (p.dc?.readyState === 'open') {
      p.dc.send(json);
    }
  }
}

  closeSocketRTC() {
    // Cerrar WebRTC peers
    for (const [id, peer] of this.peers) {
      try {
        peer.dc?.close();
      } catch {}
      try {
        peer.pc.close();
      } catch {}
    }
    this.peers.clear();
    this.localId = '';

    // Cerrar signaling
    this.signaling.close();
  }

}
