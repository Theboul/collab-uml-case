import { Component } from '@angular/core';
import { Router } from '@angular/router';
import { v4 as uuid } from 'uuid';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

@Component({
  selector: 'app-landin-page',
  imports: [CommonModule, FormsModule],
  templateUrl: './landin-page.html',
  styleUrls: ['./landin-page.css']
})
export class LandinPage {
  joinCode: string = '';

  constructor(private router: Router) {}

  crearNuevoLienzo() {
    const roomId = uuid();
    this.router.navigate(['/diagram', roomId]);
  }

  unirseAlLienzo() {
    if (this.joinCode.trim()) {
      this.router.navigate(['/diagram', this.joinCode.trim()]);
    }
  }
}
