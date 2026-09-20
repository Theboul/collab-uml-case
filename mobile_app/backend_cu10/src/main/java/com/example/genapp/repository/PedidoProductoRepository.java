package com.example.genapp.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import com.example.genapp.model.PedidoProducto;

public interface PedidoProductoRepository extends JpaRepository<PedidoProducto, Long> {
}
