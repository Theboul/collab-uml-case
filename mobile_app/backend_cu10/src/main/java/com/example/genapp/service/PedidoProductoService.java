package com.example.genapp.service;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import java.util.*;
import com.example.genapp.model.PedidoProducto;
import com.example.genapp.repository.PedidoProductoRepository;
import com.example.genapp.model.Pedido;
import com.example.genapp.repository.PedidoRepository;
import com.example.genapp.model.Producto;
import com.example.genapp.repository.ProductoRepository;

@Service
@RequiredArgsConstructor
public class PedidoProductoService {

    private final PedidoProductoRepository repository;
    private final PedidoRepository pedidoRepository;
    private final ProductoRepository productoRepository;

    public List<PedidoProducto> findAll() {
        return repository.findAll();
    }

    public Optional<PedidoProducto> findById(Long id) {
        return repository.findById(id);
    }

    public PedidoProducto save(PedidoProducto e) {
        return repository.save(e);
    }

    public void delete(Long id) {
        repository.deleteById(id);
    }

    public Optional<Pedido> findPedidoById(Long id) {
        return pedidoRepository.findById(id);
    }

    public Optional<Producto> findProductoById(Long id) {
        return productoRepository.findById(id);
    }
}
