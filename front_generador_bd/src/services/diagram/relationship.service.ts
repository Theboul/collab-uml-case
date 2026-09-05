import { Injectable } from '@angular/core';
import { DiagramService } from './diagram.service';

@Injectable({ providedIn: 'root' })
export class RelationshipService {
	private sourceElement: any = null;
	private paper: any = null;
	private clickHandler: any = null;
	private currentType: string = 'association'; // por defecto

	constructor(private diagramService: DiagramService) {}

	/**
	 * Inicia el modo de creación de relación con un tipo específico
	 */
	startLinkCreation(
		paper: any,
		containerElement: HTMLElement,
		type: string = 'association'
	): void {
		this.paper = paper;
		this.sourceElement = null;
		this.currentType = type;
		// Cambiamos el cursor para indicar el modo de creación
		containerElement.style.cursor = 'crosshair';
		// Activamos el listener para la selección de elementos
		this.clickHandler = (cellView: any) => {
			if (!this.sourceElement) {
				// Primera selección
				this.sourceElement = cellView.model;
				//console.log(`Primer elemento seleccionado para relación (${this.currentType})`);
			} else {
				// Segunda selección, creamos la relación
				this.createTypedRelationship(
					this.sourceElement.id,
					cellView.model.id,
					this.currentType
				);
				// Limpiamos estado y desactivamos el modo de creación
				this.paper.off('cell:pointerclick', this.clickHandler);
				containerElement.style.cursor = 'default';
				this.sourceElement = null;
				this.clickHandler = null;
				//console.log(`Relación creada (${this.currentType})`);
			}
		};
		this.paper.on('cell:pointerclick', this.clickHandler);
	}

	/**
	 * Crea una relación del tipo solicitado entre dos elementos
	 */
  private createTypedRelationship(sourceId: string, targetId: string, type: string) {
    this.diagramService.createTypedRelationship(sourceId, targetId, type);
  }


	/**
	 * Cancela el modo de creación de relación
	 */
	cancelLinkCreation(containerElement: HTMLElement): void {
		if (this.paper && this.clickHandler) {
			this.paper.off('cell:pointerclick', this.clickHandler);
			containerElement.style.cursor = 'default';
			this.sourceElement = null;
			this.clickHandler = null;
			this.currentType = 'association';
		}
	}
}