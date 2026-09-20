package com.example.genapp.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import com.example.genapp.model.Producto;

public interface ProductoRepository extends JpaRepository<Producto, Long> {
}
