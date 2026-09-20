package com.example.genapp.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import com.example.genapp.model.Pedido;

public interface PedidoRepository extends JpaRepository<Pedido, Long> {
}
