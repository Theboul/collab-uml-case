import { Injectable, NgZone, inject } from '@angular/core';
import { Subject } from 'rxjs';
import { Graph } from '@antv/x6';

export interface EdgeVerticesChangedEvent {
  edgeId: string;
  vertices: Array<{ x: number; y: number }>;
}

/**
 * Gestiona el tool nativo de X6 para vértices intermedios de una relación: permite
 * arrastrar los puntos existentes del trazado y agregar uno nuevo haciendo clic sobre el
 * propio path. No toca los extremos (origen/destino), que se gestionan aparte con el tool
 * de arrowhead (reconexión, ver UmlGraphService).
 */
@Injectable({
  providedIn: 'root',
})
export class UmlEdgeToolsService {
  private readonly ngZone = inject(NgZone);

  readonly verticesChanged$ = new Subject<EdgeVerticesChangedEvent>();

  private verticesToolConfig(): { name: string; args: Record<string, unknown> } {
    return {
      name: 'vertices',
      args: {
        addable: true,
        removable: true,
        snapRadius: 10,
        attrs: {
          r: 5,
          fill: '#6366f1',
          stroke: '#ffffff',
          strokeWidth: 2,
          cursor: 'move',
        },
      },
    };
  }

  /** Aristas con un arrastre de vértice en curso (entre el mousedown y el mouseup sobre el handle). */
  private readonly edgesMovingVertex = new Set<string>();

  /**
   * Adjunta el tool de vértices a toda relación (drag-to-connect o renderCells) y persiste
   * los cambios de trazado. La persistencia se emite en el mismo punto que node:moved: al
   * soltar el arrastre (batch:stop de 'move-vertex', que siempre ocurre tanto al mover como
   * al agregar un vértice), nunca en cada mousemove intermedio. Eliminar un vértice (doble
   * clic sobre su handle) no pasa por un batch, así que se detecta por el cambio de cantidad.
   */
  registerListeners(graph: Graph): void {
    graph.on('edge:added', ({ edge }) => {
      edge.addTools([this.verticesToolConfig()]);
    });

    graph.on('edge:batch:start', ({ edge, name }) => {
      if (name === 'move-vertex') this.edgesMovingVertex.add(edge.id);
    });

    graph.on('edge:batch:stop', ({ edge, name }) => {
      if (name !== 'move-vertex') return;
      this.edgesMovingVertex.delete(edge.id);
      this.ngZone.run(() => {
        this.verticesChanged$.next({ edgeId: edge.id, vertices: edge.getVertices() });
      });
    });

    // Borrado real de un vértice. `edge:vertexs:removed` no sirve para detectarlo: X6 lo emite
    // cuando una coordenada deja de estar en el array (model/edge.js), o sea también al MOVER
    // un vértice, en cada paso del arrastre. Se distingue por cantidad (bajó) y por origen: solo
    // lo que hace el usuario con la herramienta (`options.ui`), nunca una reconciliación
    // programática, y fuera de un arrastre (ahí ya persiste el batch:stop con el estado final).
    graph.on('edge:change:vertices', ({ edge, previous, current, options }) => {
      if (!options?.['ui'] || this.edgesMovingVertex.has(edge.id)) return;
      if ((current?.length ?? 0) >= (previous?.length ?? 0)) return;
      this.ngZone.run(() => {
        this.verticesChanged$.next({ edgeId: edge.id, vertices: edge.getVertices() });
      });
    });
  }
}
